"""Licensing domain, lifecycle and authorization primitives for Otimizer."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
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
        if price_cents < 0:
            raise ValueError("price_cents must be non-negative")
        return replace(self, price_cents=price_cents)

    def is_active(self, now: datetime | None = None) -> bool:
        current = _utc(now)
        return self.status == LicenseStatus.ACTIVE and self.revoked_at is None and self.starts_at <= current < self.expires_at

    def effective_status(self, now: datetime | None = None) -> LicenseStatus:
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
    def __init__(self, licenses: list[License] | None = None) -> None:
        self._licenses = {item.license_id: item for item in licenses or []}

    def save(self, license_record: License) -> None:
        self._licenses[license_record.license_id] = license_record

    def get_by_id(self, license_id: str) -> License | None:
        return self._licenses.get(license_id)

    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        matches = (item for item in self._licenses.values() if item.account_id == account_id and item.is_active(now))
        return max(matches, key=lambda item: item.expires_at, default=None)


class InMemoryLicenseEventRepository:
    def __init__(self, events: list[LicenseEvent] | None = None) -> None:
        self._events = list(events or [])

    def append(self, event: LicenseEvent) -> None:
        self._events.append(event)

    def list_for_license(self, license_id: str) -> list[LicenseEvent]:
        return [event for event in self._events if event.license_id == license_id]


def generate_license_key() -> str:
    return token_urlsafe(32)


def create_license_event(license_id: str, action: str, occurred_at: datetime, *, actor_account_id: str | None = None, previous_status: LicenseStatus | None = None, new_status: LicenseStatus | None = None, reason: str | None = None, metadata_json: str | None = None) -> LicenseEvent:
    return LicenseEvent(token_urlsafe(18), license_id, action, _utc(occurred_at), actor_account_id, previous_status, new_status, reason, metadata_json)


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    code: str
    message: str
    license: License | None = None


class LicenseAuthorizer:
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


class LicenseLifecycleError(ValueError):
    """Raised when a requested commercial transition is not allowed."""


class LicenseLifecycleService:
    """Authoritative server-side license state machine.

    All transitions are explicit and produce an audit event. The service never
    trusts client clocks and never permits a revoked license to be reactivated.
    """

    def __init__(self, repository: LicenseRepository, events: LicenseEventRepository) -> None:
        self.repository = repository
        self.events = events

    def activate(self, license_id: str, actor_account_id: str, now: datetime | None = None) -> License:
        return self._transition(license_id, actor_account_id, "ACTIVATED", LicenseStatus.ACTIVE, now, allowed={LicenseStatus.GENERATED, LicenseStatus.AVAILABLE}, set_activated=True)

    def renew(self, license_id: str, actor_account_id: str, duration: timedelta, now: datetime | None = None) -> License:
        current = _utc(now)
        if duration <= timedelta(0):
            raise LicenseLifecycleError("renewal duration must be positive")
        record = self._get(license_id)
        status = record.effective_status(current)
        if status in {LicenseStatus.REVOKED, LicenseStatus.SUSPENDED}:
            raise LicenseLifecycleError(f"license cannot be renewed while {status.value}")
        base = max(record.expires_at, current)
        updated = replace(record, expires_at=base + duration, status=LicenseStatus.ACTIVE, last_renewal_at=current, renewal_count=record.renewal_count + 1)
        self.repository.save(updated)
        self.events.append(create_license_event(license_id, "RENEWED", current, actor_account_id=actor_account_id, previous_status=record.status, new_status=updated.status, metadata_json=f'{{"duration_seconds":{int(duration.total_seconds())}}}'))
        return updated

    def suspend(self, license_id: str, actor_account_id: str, reason: str, now: datetime | None = None) -> License:
        if not reason.strip():
            raise LicenseLifecycleError("suspension reason is required")
        return self._transition(license_id, actor_account_id, "SUSPENDED", LicenseStatus.SUSPENDED, now, allowed={LicenseStatus.ACTIVE}, reason=reason)

    def reactivate(self, license_id: str, actor_account_id: str, now: datetime | None = None) -> License:
        current = _utc(now)
        record = self._get(license_id)
        if record.status != LicenseStatus.SUSPENDED:
            raise LicenseLifecycleError("only suspended licenses can be reactivated")
        if current >= record.expires_at:
            raise LicenseLifecycleError("expired license cannot be reactivated; renew it first")
        return self._transition(license_id, actor_account_id, "REACTIVATED", LicenseStatus.ACTIVE, current, allowed={LicenseStatus.SUSPENDED})

    def revoke(self, license_id: str, actor_account_id: str, reason: str, now: datetime | None = None) -> License:
        if not reason.strip():
            raise LicenseLifecycleError("revocation reason is required")
        current = _utc(now)
        record = self._get(license_id)
        if record.status == LicenseStatus.REVOKED or record.revoked_at is not None:
            raise LicenseLifecycleError("license is already revoked")
        updated = replace(record, status=LicenseStatus.REVOKED, revoked_at=current)
        self.repository.save(updated)
        self.events.append(create_license_event(license_id, "REVOKED", current, actor_account_id=actor_account_id, previous_status=record.status, new_status=LicenseStatus.REVOKED, reason=reason))
        return updated

    def expire(self, license_id: str, now: datetime | None = None) -> License:
        current = _utc(now)
        record = self._get(license_id)
        if record.status == LicenseStatus.REVOKED:
            raise LicenseLifecycleError("revoked license cannot be expired")
        if current < record.expires_at:
            raise LicenseLifecycleError("license has not reached expiration")
        if record.status == LicenseStatus.EXPIRED:
            return record
        updated = replace(record, status=LicenseStatus.EXPIRED)
        self.repository.save(updated)
        self.events.append(create_license_event(license_id, "EXPIRED", current, previous_status=record.status, new_status=LicenseStatus.EXPIRED))
        return updated

    def _transition(self, license_id: str, actor_account_id: str, action: str, new_status: LicenseStatus, now: datetime | None, *, allowed: set[LicenseStatus], reason: str | None = None, set_activated: bool = False) -> License:
        current = _utc(now)
        record = self._get(license_id)
        effective = record.effective_status(current)
        if effective == LicenseStatus.EXPIRED:
            raise LicenseLifecycleError("expired license must be renewed before activation")
        if record.status not in allowed:
            raise LicenseLifecycleError(f"transition {record.status.value} -> {new_status.value} is not allowed")
        updated = replace(record, status=new_status, activated_at=current if set_activated else record.activated_at)
        self.repository.save(updated)
        self.events.append(create_license_event(license_id, action, current, actor_account_id=actor_account_id, previous_status=record.status, new_status=new_status, reason=reason))
        return updated

    def _get(self, license_id: str) -> License:
        record = self.repository.get_by_id(license_id)
        if record is None:
            raise LicenseLifecycleError("license not found")
        return record


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
