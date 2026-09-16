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
    return ["http://localhost:3000", "http://localhost:5173", "http://localhost:8080", "http://127.0.0.1:8080"]


def _endpoint(latitude: float | None, longitude: float | None, name: str) -> RouteEndpoint | None:
    if latitude is None and longitude is None:
        return None
    if latitude is None or longitude is None:
        raise HTTPException(status_code=400, detail=f"{name} latitude and longitude must be provided together")
    return RouteEndpoint(latitude=latitude, longitude=longitude, name=name)
