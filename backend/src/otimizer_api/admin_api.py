"""Protected administrative API for commercial licensing operations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from .accounts import AccountRole
from .auth import AuthenticationService
from .devices import DeviceRepository
from .licensing import Entitlements, License, LicenseEventRepository, LicenseLifecycleError, LicenseLifecycleService, LicenseRepository, LicenseStatus, create_license_event


class LicenseGenerateRequest(BaseModel):
    account_id: str = Field(min_length=1)
    plan: str = Field(default="default", min_length=1, max_length=100)
    duration_days: int = Field(gt=0, le=3650)
    max_devices: int = Field(default=1, ge=1, le=1000)
    max_routes_per_day: int | None = Field(default=None, ge=1)
    route_optimization: bool = True
    price_cents: int = Field(default=0, ge=0)
    starts_at: datetime | None = None

class RenewalRequest(BaseModel):
    duration_days: int = Field(gt=0, le=3650)

class ReasonRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


def _serialize_license(record: License, now: datetime | None = None) -> dict:
    current = now or datetime.now(timezone.utc)
    return {"license_id":record.license_id,"license_key":record.license_key,"account_id":record.account_id,"plan":record.plan,"status":record.effective_status(current).value,"starts_at":record.starts_at.isoformat(),"expires_at":record.expires_at.isoformat(),"activated_at":record.activated_at.isoformat() if record.activated_at else None,"last_renewal_at":record.last_renewal_at.isoformat() if record.last_renewal_at else None,"renewal_count":record.renewal_count,"last_access_at":record.last_access_at.isoformat() if record.last_access_at else None,"revoked_at":record.revoked_at.isoformat() if record.revoked_at else None,"price_cents":record.price_cents,"entitlements":{"route_optimization":record.entitlements.route_optimization,"max_devices":record.entitlements.max_devices,"max_routes_per_day":record.entitlements.max_routes_per_day}}

def _serialize_event(event) -> dict:
    return {"event_id":event.event_id,"license_id":event.license_id,"action":event.action,"occurred_at":event.occurred_at.isoformat(),"actor_account_id":event.actor_account_id,"previous_status":event.previous_status.value if event.previous_status else None,"new_status":event.new_status.value if event.new_status else None,"reason":event.reason,"metadata_json":event.metadata_json}

def _serialize_device(device) -> dict:
    return {"device_id":device.device_id,"account_id":device.account_id,"license_id":device.license_id,"created_at":device.created_at.isoformat(),"last_seen_at":device.last_seen_at.isoformat(),"revoked_at":device.revoked_at.isoformat() if device.revoked_at else None,"active":device.active}

def _list_licenses(repository: LicenseRepository) -> list[License]:
    list_all=getattr(repository,"list_all",None)
    if callable(list_all): return list(list_all())
    database=getattr(repository,"database",None)
    if database is not None:
        from .persistence import _LICENSE_SELECT,_license_from_row
        with database.connect() as connection: rows=connection.execute(_LICENSE_SELECT+" ORDER BY expires_at DESC, license_id ASC").fetchall()
        return [_license_from_row(row) for row in rows]
    internal=getattr(repository,"_licenses",None)
    if isinstance(internal,dict): return list(internal.values())
    raise RuntimeError("license repository does not support administrative listing")


def register_admin_routes(api, *, auth_service: AuthenticationService, licenses: LicenseRepository, events: LicenseEventRepository, lifecycle: LicenseLifecycleService, devices: DeviceRepository) -> None:
    def require_admin(authorization: str | None):
        authenticated=auth_service.authenticate_bearer(authorization)
        if authenticated is None: raise HTTPException(status_code=401, detail="Authentication is required")
        if authenticated.account.role != AccountRole.ADMIN: raise HTTPException(status_code=403, detail="Administrator role is required")
        return authenticated.account
    def transition(call):
        try: return call()
        except LicenseLifecycleError as exc:
            message=str(exc); status=404 if message=="license not found" else 409
            raise HTTPException(status_code=status, detail=message) from exc

    @api.post("/admin/licenses")
    def generate_license(payload: LicenseGenerateRequest, authorization: str | None = Header(default=None)) -> dict:
        admin=require_admin(authorization); account=auth_service.accounts.get_by_id(payload.account_id.strip())
        if account is None: raise HTTPException(status_code=404, detail="Account not found")
        starts=(payload.starts_at or datetime.now(timezone.utc)).astimezone(timezone.utc); record=License(license_id=token_urlsafe(18),account_id=account.account_id,starts_at=starts,expires_at=starts+timedelta(days=payload.duration_days),entitlements=Entitlements(route_optimization=payload.route_optimization,max_devices=payload.max_devices,max_routes_per_day=payload.max_routes_per_day),price_cents=payload.price_cents,license_key=token_urlsafe(32),status=LicenseStatus.GENERATED,plan=payload.plan.strip())
        occurred=datetime.now(timezone.utc); event=create_license_event(record.license_id,"GENERATED",occurred,actor_account_id=admin.account_id,new_status=LicenseStatus.GENERATED)
        atomic=getattr(licenses,"save_with_event",None)
        if callable(atomic): atomic(record,event)
        else: licenses.save(record); events.append(event)
        return _serialize_license(record)

    @api.get("/admin/licenses")
    def list_licenses(account_id: str | None = None, status: LicenseStatus | None = None, authorization: str | None = Header(default=None)) -> dict:
        require_admin(authorization); records=_list_licenses(licenses); now=datetime.now(timezone.utc)
        if account_id: records=[item for item in records if item.account_id==account_id]
        if status: records=[item for item in records if item.effective_status(now)==status]
        records.sort(key=lambda item:(item.expires_at,item.license_id),reverse=True)
        return {"items":[_serialize_license(item,now) for item in records],"count":len(records)}

    @api.get("/admin/licenses/{license_id}")
    def get_license(license_id: str, authorization: str | None = Header(default=None)) -> dict:
        require_admin(authorization); record=licenses.get_by_id(license_id)
        if record is None: raise HTTPException(status_code=404,detail="License not found")
        return _serialize_license(record)

    @api.get("/admin/licenses/{license_id}/history")
    def license_history(license_id: str, authorization: str | None = Header(default=None)) -> dict:
        require_admin(authorization)
        if licenses.get_by_id(license_id) is None: raise HTTPException(status_code=404,detail="License not found")
        history=events.list_for_license(license_id)
        return {"items":[_serialize_event(event) for event in history],"count":len(history)}

    @api.post("/admin/licenses/{license_id}/activate")
    def activate_license(license_id: str, authorization: str | None = Header(default=None)) -> dict:
        admin=require_admin(authorization); return _serialize_license(transition(lambda:lifecycle.activate(license_id,admin.account_id)))
    @api.post("/admin/licenses/{license_id}/renew")
    def renew_license(license_id: str,payload: RenewalRequest,authorization: str | None=Header(default=None)) -> dict:
        admin=require_admin(authorization); return _serialize_license(transition(lambda:lifecycle.renew(license_id,admin.account_id,timedelta(days=payload.duration_days))))
    @api.post("/admin/licenses/{license_id}/suspend")
    def suspend_license(license_id: str,payload: ReasonRequest,authorization: str | None=Header(default=None)) -> dict:
        admin=require_admin(authorization); return _serialize_license(transition(lambda:lifecycle.suspend(license_id,admin.account_id,payload.reason)))
    @api.post("/admin/licenses/{license_id}/reactivate")
    def reactivate_license(license_id: str,authorization: str | None=Header(default=None)) -> dict:
        admin=require_admin(authorization); return _serialize_license(transition(lambda:lifecycle.reactivate(license_id,admin.account_id)))
    @api.post("/admin/licenses/{license_id}/revoke")
    def revoke_license(license_id: str,payload: ReasonRequest,authorization: str | None=Header(default=None)) -> dict:
        admin=require_admin(authorization); return _serialize_license(transition(lambda:lifecycle.revoke(license_id,admin.account_id,payload.reason)))
    @api.get("/admin/licenses/{license_id}/devices")
    def list_devices(license_id: str,authorization: str | None=Header(default=None)) -> dict:
        require_admin(authorization)
        if licenses.get_by_id(license_id) is None: raise HTTPException(status_code=404,detail="License not found")
        items=devices.list_for_license(license_id,active_only=False)
        return {"items":[_serialize_device(item) for item in items],"count":len(items)}
    @api.post("/admin/devices/{device_id}/revoke")
    def revoke_device(device_id: str,authorization: str | None=Header(default=None)) -> dict:
        admin=require_admin(authorization); device=devices.get(device_id)
        if device is None: raise HTTPException(status_code=404,detail="Device not found")
        if device.revoked_at is not None: raise HTTPException(status_code=409,detail="Device is already revoked")
        occurred=datetime.now(timezone.utc)
        event=create_license_event(device.license_id,"DEVICE_REVOKED_BY_ADMIN",occurred,actor_account_id=admin.account_id,metadata_json=f'{{"device_id":"{device_id}"}}')
        atomic=getattr(devices,"revoke_with_event",None)
        if callable(atomic):
            revoked=atomic(device_id,occurred,event)
        else:
            revoked=devices.revoke(device_id,occurred)
            if revoked is not None: events.append(event)
        if revoked is None: raise HTTPException(status_code=404,detail="Device not found or already revoked")
        return _serialize_device(revoked)
