"""Licensing domain, lifecycle and authorization primitives for Otimizer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import StrEnum
from secrets import token_urlsafe
from typing import Protocol


class LicenseStatus(StrEnum):
    GENERATED = "GERADA"
    AVAILABLE = "DISPONIVEL"
    ACTIVE = "ATIVA"
    EXPIRED = "EXPIRADA"
    SUSPENDED = "SUSPENSA"
    REVOKED = "REVOGADA"


@dataclass(frozen=True)
class Entitlements:
    """Features and limits granted by a license plan."""

    route_optimization: bool = True
    max_devices: int = 1
    max_routes_per_day: int | None = None

    def __post_init__(self) -> None:
        if self.max_devices < 1:
            raise ValueError("max_devices must be at least 1")
        if self.max_routes_per_day is not None and self.max_routes_per_day < 1:
            raise ValueError("max_routes_per_day must be positive when configured")


@dataclass(frozen=True)
class License:
    """Server-owned commercial license record.

    ``license_id`` is an internal identifier. ``license_key`` is the
    unpredictable customer-facing activation credential and is never used as
    the database primary key.
    """

    license_id: str
    account_id: str
    starts_at: datetime
    expires_at: datetime
    entitlements: Entitlements = field(default_factory=Entitlements)
    revoked_at: datetime | None = None
    price_cents: int = 0
    license_key: str = field(default_factory=lambda: generate_license_key())
    status: LicenseStatus = LicenseStatus.ACTIVE
    activated_at: datetime | None = None
    last_renewal_at: datetime | None = None
    renewal_count: int = 0
    last_access_at: datetime | None = None
    plan: str = "default"

    def __post_init__(self) -> None:
        if not self.license_id.strip():
            raise ValueError("license_id must not be empty")
        if not self.account_id.strip():
            raise ValueError("account_id must not be empty")
        if not self.license_key.strip():
            raise ValueError("license_key must not be empty")
        if self.price_cents < 0:
            raise ValueError("price_cents must be non-negative")
        if self.renewal_count < 0:
            raise ValueError("renewal_count must be non-negative")
        if self.status == LicenseStatus.REVOKED and self.revoked_at is None:
            raise ValueError("revoked licenses require revoked_at")

    def change_price(self, price_cents: int) -> "License":
        """Return this license with a new configured price without mutation."""
        if price_cents < 0:
            raise ValueError("price_cents must be non-negative")
        return replace(self, price_cents=price_cents)

    def is_active(self, now: datetime | None = None) -> bool:
        current = _utc(now)
        return (
            self.status == LicenseStatus.ACTIVE
            and self.revoked_at is None
            and self.starts_at <= current < self.expires_at
        )

    def effective_status(self, now: datetime | None = None) -> LicenseStatus:
        """Return the operational state using backend/server time."""
        current = _utc(now)
        if self.status == LicenseStatus.REVOKED or self.revoked_at is not None:
            return LicenseStatus.REVOKED
        if self.status == LicenseStatus.SUSPENDED:
            return LicenseStatus.SUSPENDED
        if current >= self.expires_at:
            return LicenseStatus.EXPIRED
        return self.status


@dataclass(frozen=True)
class LicenseEvent:
    """Immutable audit event for a license lifecycle transition/action."""

    event_id: str
    license_id: str
    action: str
    occurred_at: datetime
    actor_account_id: str | None = None
    previous_status: LicenseStatus | None = None
    new_status: LicenseStatus | None = None
    reason: str | None = None
    metadata_json: str | None = None


class LicenseRepository(Protocol):
    def get_active_license(self, account_id: str, now: datetime) -> License | None: ...
    def get_by_id(self, license_id: str) -> License | None: ...
    def save(self, license_record: License) -> None: ...


class LicenseEventRepository(Protocol):
    def append(self, event: LicenseEvent) -> None: ...
    def list_for_license(self, license_id: str) -> list[LicenseEvent]: ...


class InMemoryLicenseRepository:
    """Development repository; replace with a database adapter in production."""

    def __init__(self, licenses: list[License] | None = None) -> None:
        self._licenses = {item.license_id: item for item in licenses or []}

    def save(self, license_record: License) -> None:
        self._licenses[license_record.license_id] = license_record

    def get_by_id(self, license_id: str) -> License | None:
        return self._licenses.get(license_id)

    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        matches = (
            license_record
            for license_record in self._licenses.values()
            if license_record.account_id == account_id and license_record.is_active(now)
        )
        return max(matches, key=lambda item: item.expires_at, default=None)


class InMemoryLicenseEventRepository:
    def __init__(self, events: list[LicenseEvent] | None = None) -> None:
        self._events = list(events or [])

    def append(self, event: LicenseEvent) -> None:
        self._events.append(event)

    def list_for_license(self, license_id: str) -> list[LicenseEvent]:
        return [event for event in self._events if event.license_id == license_id]


def generate_license_key() -> str:
    """Generate a high-entropy customer-facing license key."""
    return token_urlsafe(32)


def create_license_event(
    license_id: str,
    action: str,
    occurred_at: datetime,
    *,
    actor_account_id: str | None = None,
    previous_status: LicenseStatus | None = None,
    new_status: LicenseStatus | None = None,
    reason: str | None = None,
    metadata_json: str | None = None,
) -> LicenseEvent:
    return LicenseEvent(
        event_id=token_urlsafe(18),
        license_id=license_id,
        action=action,
        occurred_at=_utc(occurred_at),
        actor_account_id=actor_account_id,
        previous_status=previous_status,
        new_status=new_status,
        reason=reason,
        metadata_json=metadata_json,
    )


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    code: str
    message: str
    license: License | None = None


class LicenseAuthorizer:
    """Authorize protected operations using server time and entitlements."""

    def __init__(self, repository: LicenseRepository) -> None:
        self.repository = repository

    def authorize_route(self, account_id: str, now: datetime | None = None) -> LicenseDecision:
        current = _utc(now)
        license_record = self.repository.get_active_license(account_id, current)
        if license_record is None:
            return LicenseDecision(False, "LICENSE_REQUIRED", "A valid license is required to generate a route.")
        if not license_record.entitlements.route_optimization:
            return LicenseDecision(False, "FEATURE_NOT_ENTITLED", "The current plan does not allow route optimization.", license_record)
        return LicenseDecision(True, "AUTHORIZED", "Route optimization authorized.", license_record)


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
