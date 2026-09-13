"""Licensing domain and authorization primitives for Otimizer.

The production implementation will persist these objects in a database and
receive trusted payment confirmations from a payment provider. This module
keeps route authorization independent from the future persistence layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol


@dataclass(frozen=True)
class Entitlements:
    """Features and limits granted by a license plan."""

    route_optimization: bool = True
    max_devices: int = 1
    max_routes_per_day: int | None = None


@dataclass(frozen=True)
class License:
    """A server-owned license record.

    ``price_cents`` is the configured price for this license. It is stored on
    the license itself so later price changes do not alter historical charges.
    """

    license_id: str
    account_id: str
    starts_at: datetime
    expires_at: datetime
    entitlements: Entitlements = field(default_factory=Entitlements)
    revoked_at: datetime | None = None
    price_cents: int = 0

    def __post_init__(self) -> None:
        if self.price_cents < 0:
            raise ValueError("price_cents must be non-negative")

    def is_active(self, now: datetime | None = None) -> bool:
        current = _utc(now)
        return self.revoked_at is None and self.starts_at <= current < self.expires_at


@dataclass(frozen=True)
class LicenseDecision:
    allowed: bool
    code: str
    message: str
    license: License | None = None


class LicenseRepository(Protocol):
    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        """Return the currently active license for an account, if any."""


class InMemoryLicenseRepository:
    """Development repository; replace with a database adapter in production."""

    def __init__(self, licenses: list[License] | None = None) -> None:
        self._licenses = list(licenses or [])

    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        matches = (
            license_record
            for license_record in self._licenses
            if license_record.account_id == account_id and license_record.is_active(now)
        )
        return max(matches, key=lambda item: item.expires_at, default=None)


class LicenseAuthorizer:
    """Authorize protected operations using server time and entitlements."""

    def __init__(self, repository: LicenseRepository) -> None:
        self.repository = repository

    def authorize_route(self, account_id: str, now: datetime | None = None) -> LicenseDecision:
        current = _utc(now)
        license_record = self.repository.get_active_license(account_id, current)
        if license_record is None:
            return LicenseDecision(
                allowed=False,
                code="LICENSE_REQUIRED",
                message="A valid license is required to generate a route.",
            )
        if not license_record.entitlements.route_optimization:
            return LicenseDecision(
                allowed=False,
                code="FEATURE_NOT_ENTITLED",
                message="The current plan does not allow route optimization.",
                license=license_record,
            )
        return LicenseDecision(
            allowed=True,
            code="AUTHORIZED",
            message="Route optimization authorized.",
            license=license_record,
        )


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
