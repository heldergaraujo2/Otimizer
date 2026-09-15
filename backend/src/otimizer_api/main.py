from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from otimizer_importer import OptimizationObjective, RouteEndpoint, optimize_deliveries_file
from otimizer_importer.location import LocationDataProvider
from otimizer_importer.optimization import OptimizationError
from otimizer_importer.routing import RoutingError, RoutingProvider
from otimizer_api.auth import AuthenticationService
from otimizer_api.licensing import LicenseAuthorizer
from otimizer_api.payments import PaymentService

DEFAULT_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class LoginRequest(BaseModel):
    email: str
    password: str


class PixChargeRequest(BaseModel):
    license_id: str


def _max_upload_bytes() -> int:
    raw = os.getenv("OTIMIZER_MAX_UPLOAD_BYTES")
    if raw is None:
        return DEFAULT_MAX_UPLOAD_BYTES
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_MAX_UPLOAD_BYTES
    return max(1, value)


def _cors_origins() -> list[str]:
    raw = os.getenv("OTIMIZER_CORS_ORIGINS")
    if raw:
        origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
        if origins:
            return origins
    return ["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"]


def _endpoint(latitude: float | None, longitude: float | None, name: str) -> RouteEndpoint | None:
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail=f"{name} requires both latitude and longitude")
    return RouteEndpoint(latitude, longitude, name)


def _serialize_charge(charge) -> dict:
    return {
        "payment_id": charge.payment_id,
        "license_id": charge.license_id,
        "amount_cents": charge.amount_cents,
        "expires_at": charge.expires_at.isoformat(),
        "pix_copy_paste": charge.pix_copy_paste,
        "status": charge.status.value,
    }


def _serialize_license(license_record, now=None) -> dict:
    current = now or datetime.now(timezone.utc)
    return {
        "license_id": license_record.license_id,
        "account_id": license_record.account_id,
        "starts_at": license_record.starts_at.isoformat(),
        "expires_at": license_record.expires_at.isoformat(),
        "active": license_record.is_active(current),
        "revoked": license_record.revoked_at is not None,
        "price_cents": license_record.price_cents,
        "entitlements": {
            "route_optimization": license_record.entitlements.route_optimization,
            "max_devices": license_record.entitlements.max_devices,
            "max_routes_per_day": license_record.entitlements.max_routes_per_day,
        },
    }


def _serialize(result) -> dict:
    return {
        "summary": {
            "eligible_deliveries": result.eligible_delivery_count,
            "routed_deliveries": result.routed_delivery_count,
            "physical_stops": result.physical_stop_count,
            "routed_stops": result.routed_stop_count,
            "pending": result.pending_count,
            "coverage_complete": result.coverage_complete,
            "fully_resolved": result.fully_resolved,
            "distance_meters": result.route_metrics.distance_meters,
            "duration_seconds": result.route_metrics.duration_seconds,
        },
        "unresolved_rows": list(result.unresolved_rows),
        "route": [
            {
                "sequence": stop.sequence,
                "id": stop.id,
                "latitude": stop.physical_stop.latitude,
                "longitude": stop.physical_stop.longitude,
                "location": {
                    "confidence": stop.physical_stop.location_confidence,
                    "source": stop.physical_stop.location_source,
                    "property_latitude": stop.physical_stop.property_latitude,
                    "property_longitude": stop.physical_stop.property_longitude,
                    "access_latitude": stop.physical_stop.access_latitude,
                    "access_longitude": stop.physical_stop.access_longitude,
                    "cadastral_id": stop.physical_stop.cadastral_id,
                },
                "delivery_count": stop.delivery_count,
                "deliveries": [
                    {
                        "row_number": delivery.row_number,
                        "tracking_number": delivery.tracking_number,
                        "source_id": delivery.source_id,
                        "source_sequence": delivery.source_sequence,
                        "source_stop": delivery.source_stop,
                        "address": delivery.address,
                        "neighborhood": delivery.neighborhood,
                        "city": delivery.city,
                        "zipcode": delivery.zipcode,
                        "quadra": delivery.quadra,
                        "lote": delivery.lote,
                        "latitude": delivery.latitude,
                        "longitude": delivery.longitude,
                    }
                    for delivery in stop.physical_stop.deliveries
                ],
            }
            for stop in result.route.stops
        ],
        "legs": [
            {
                "from_id": leg.from_id,
                "to_id": leg.to_id,
                "distance_meters": leg.distance_meters,
                "duration_seconds": leg.duration_seconds,
            }
            for leg in result.route_metrics.legs
        ],
    }


def create_app(
    routing_provider: RoutingProvider | None = None,
    license_authorizer: LicenseAuthorizer | None = None,
    auth_service: AuthenticationService | None = None,
    payment_service: PaymentService | None = None,
    location_provider: LocationDataProvider | None = None,
) -> FastAPI:
    api = FastAPI(title="Otimizer API", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Otimizer-Account-ID"],
    )

    def authenticated_account(authorization: str | None):
        if auth_service is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        authenticated = auth_service.authenticate_bearer(authorization)
        if authenticated is None:
            raise HTTPException(status_code=401, detail="Authentication is required")
        return authenticated.account

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/auth/login")
    def login(payload: LoginRequest) -> dict:
        if auth_service is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        result = auth_service.login(payload.email, payload.password)
        if result is None:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        account, token = result
        return {
            "access_token": token,
            "token_type": "bearer",
            "account": {"account_id": account.account_id, "email": account.email},
        }

    @api.get("/auth/me")
    def me(authorization: Annotated[str | None, Header()] = None) -> dict:
        account = authenticated_account(authorization)
        return {"account_id": account.account_id, "email": account.email}

    @api.post("/auth/logout")
    def logout(authorization: Annotated[str | None, Header()] = None) -> dict[str, bool]:
        if auth_service is None:
            raise HTTPException(status_code=503, detail="Authentication is not configured")
        if not auth_service.logout(authorization):
            raise HTTPException(status_code=401, detail="Authentication is required")
        return {"logged_out": True}

    @api.get("/licenses/me")
    def my_license(authorization: Annotated[str | None, Header()] = None) -> dict:
        account = authenticated_account(authorization)
        if license_authorizer is None:
            raise HTTPException(status_code=503, detail="Licensing is not configured")
        license_record = license_authorizer.repository.get_active_license(
            account.account_id, datetime.now(timezone.utc)
        )
        if license_record is None:
            return {"active": False, "license": None}
        return {"active": True, "license": _serialize_license(license_record)}

    @api.post("/payments/pix")
    def create_pix_charge(
        payload: PixChargeRequest,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict:
        account = authenticated_account(authorization)
        if payment_service is None or payment_service.license_repository is None:
            raise HTTPException(status_code=503, detail="Payments are not configured")
        license_record = payment_service.license_repository.get_by_id(payload.license_id.strip())
        if license_record is None or license_record.account_id != account.account_id:
            raise HTTPException(status_code=404, detail="License not found")
        try:
            charge = payment_service.create_license_charge(license_record)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return _serialize_charge(charge)

    @api.get("/payments/pix/{payment_id}")
    def get_pix_charge(
        payment_id: str,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict:
        account = authenticated_account(authorization)
        if payment_service is None:
            raise HTTPException(status_code=503, detail="Payments are not configured")
        charge = payment_service.repository.get(payment_id)
        if charge is None or charge.account_id != account.account_id:
            raise HTTPException(status_code=404, detail="Payment not found")
        return _serialize_charge(charge)

    @api.post("/optimize")
    async def optimize_route(
        file: Annotated[UploadFile, File(...)],
        objective: Annotated[OptimizationObjective, Form()] = OptimizationObjective.TIME,
        origin_latitude: Annotated[float | None, Form()] = None,
        origin_longitude: Annotated[float | None, Form()] = None,
        destination_latitude: Annotated[float | None, Form()] = None,
        destination_longitude: Annotated[float | None, Form()] = None,
        return_to_start: Annotated[bool, Form()] = False,
        authorization: Annotated[str | None, Header()] = None,
        account_id: Annotated[str | None, Header(alias="X-Otimizer-Account-ID")] = None,
    ) -> dict:
        if auth_service is not None:
            authenticated = auth_service.authenticate_bearer(authorization)
            if authenticated is None:
                raise HTTPException(status_code=401, detail="Authentication is required")
            account_id = authenticated.account.account_id

        if license_authorizer is not None:
            if not account_id or not account_id.strip():
                raise HTTPException(status_code=401, detail="Authentication is required")
            decision = license_authorizer.authorize_route(account_id.strip())
            if not decision.allowed:
                raise HTTPException(status_code=403, detail={"code": decision.code, "message": decision.message})

        if not file.filename or Path(file.filename).suffix.lower() != ".xlsx":
            raise HTTPException(status_code=422, detail="The uploaded file must be an .xlsx workbook")
        origin = _endpoint(origin_latitude, origin_longitude, "origin")
        destination = _endpoint(destination_latitude, destination_longitude, "destination")
        if destination is not None and return_to_start:
            raise HTTPException(status_code=422, detail="destination and return_to_start cannot be combined")

        max_bytes = _max_upload_bytes()
        contents = await file.read(max_bytes + 1)
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail=f"Uploaded file exceeds the {max_bytes} byte limit")

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        try:
            result = optimize_deliveries_file(
                str(temporary_path), routing_provider=routing_provider,
                location_provider=location_provider, origin=origin,
                destination=destination, return_to_start=return_to_start, objective=objective,
            )
        except RoutingError as exc:
            raise HTTPException(status_code=502, detail=f"Routing provider failed: {exc}") from exc
        except OptimizationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (ValueError, OSError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            temporary_path.unlink(missing_ok=True)
        return _serialize(result)

    return api


from otimizer_api.persistence import SQLitePaymentRepository, build_sqlite_services
from otimizer_api.payments import SandboxPixGateway
from otimizer_importer.goiania import GoianiaLocationProvider


def _database_path() -> Path:
    configured = os.getenv("OTIMIZER_DB_PATH")
    if configured and configured.strip():
        return Path(configured.strip())
    return Path.home() / ".otimizer" / "otimizer.db"


_database, _auth_service, _license_authorizer = build_sqlite_services(_database_path())
_payment_repository = SQLitePaymentRepository(_database)
_payment_gateway = SandboxPixGateway(_payment_repository)
_payment_service = PaymentService(
    _payment_repository,
    _payment_gateway,
    _license_authorizer.repository,
)
_location_provider = GoianiaLocationProvider()

app = create_app(
    auth_service=_auth_service,
    license_authorizer=_license_authorizer,
    payment_service=_payment_service,
    location_provider=_location_provider,
)