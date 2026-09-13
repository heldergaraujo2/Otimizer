"""Provider-neutral Pix payment domain with a deterministic sandbox gateway."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol
from uuid import uuid4

from .licensing import License, LicenseRepository


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SETTLED = "settled"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class PixCharge:
    payment_id: str
    account_id: str
    license_id: str
    amount_cents: int
    expires_at: datetime
    pix_copy_paste: str
    status: PaymentStatus = PaymentStatus.PENDING


class PaymentRepository(Protocol):
    def save(self, charge: PixCharge) -> None: ...
    def get(self, payment_id: str) -> PixCharge | None: ...


class InMemoryPaymentRepository:
    def __init__(self) -> None:
        self._charges: dict[str, PixCharge] = {}

    def save(self, charge: PixCharge) -> None:
        self._charges[charge.payment_id] = charge

    def get(self, payment_id: str) -> PixCharge | None:
        return self._charges.get(payment_id)


class PixGateway(Protocol):
    def create_charge(
        self,
        account_id: str,
        license_id: str,
        amount_cents: int,
        expires_in: timedelta,
    ) -> PixCharge: ...

    def confirm_sandbox_charge(self, payment_id: str) -> PixCharge: ...


class SandboxPixGateway:
    """Fake Pix gateway used for automated and manual end-to-end tests."""

    def __init__(self, repository: PaymentRepository) -> None:
        self.repository = repository

    def create_charge(
        self,
        account_id: str,
        license_id: str,
        amount_cents: int,
        expires_in: timedelta,
    ) -> PixCharge:
        if not account_id:
            raise ValueError("account_id is required")
        if not license_id:
            raise ValueError("license_id is required")
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if expires_in <= timedelta(0):
            raise ValueError("expires_in must be positive")
        now = datetime.now(timezone.utc)
        payment_id = str(uuid4())
        charge = PixCharge(
            payment_id=payment_id,
            account_id=account_id,
            license_id=license_id,
            amount_cents=amount_cents,
            expires_at=now + expires_in,
            pix_copy_paste=f"otimizer-sandbox-pix:{payment_id}",
        )
        self.repository.save(charge)
        return charge

    def confirm_sandbox_charge(self, payment_id: str) -> PixCharge:
        charge = self.repository.get(payment_id)
        if charge is None:
            raise KeyError(payment_id)
        if charge.status != PaymentStatus.PENDING:
            return charge
        if datetime.now(timezone.utc) >= charge.expires_at:
            expired = replace(charge, status=PaymentStatus.EXPIRED)
            self.repository.save(expired)
            return expired
        confirmed = replace(charge, status=PaymentStatus.CONFIRMED)
        self.repository.save(confirmed)
        return confirmed


class PaymentService:
    """Create charges and settle trusted provider confirmations."""

    def __init__(
        self,
        repository: PaymentRepository,
        gateway: PixGateway,
        license_repository: LicenseRepository | None = None,
    ) -> None:
        self.repository = repository
        self.gateway = gateway
        self.license_repository = license_repository

    def create_license_charge(
        self,
        license_record: License,
        expires_in: timedelta = timedelta(minutes=30),
    ) -> PixCharge:
        if license_record.price_cents <= 0:
            raise ValueError("license price must be positive before creating a Pix charge")
        return self.gateway.create_charge(
            license_record.account_id,
            license_record.license_id,
            license_record.price_cents,
            expires_in,
        )

    def settle_confirmed_payment(
        self,
        payment_id: str,
        now: datetime | None = None,
    ) -> License:
        """Activate a license after trusted payment confirmation.

        A real PSP webhook should first validate its signature and amount, then
        persist the payment as ``CONFIRMED`` before calling this method. The
        sandbox gateway provides the same trusted confirmation for tests.
        ``SETTLED`` makes repeated webhook delivery idempotent.
        """
        if self.license_repository is None:
            raise RuntimeError("license_repository is required for settlement")
        charge = self.repository.get(payment_id)
        if charge is None:
            raise KeyError(payment_id)
        license_record = self.license_repository.get_by_id(charge.license_id)
        if license_record is None or license_record.account_id != charge.account_id:
            raise ValueError("payment is not bound to a valid account license")
        if charge.status == PaymentStatus.SETTLED:
            return license_record
        if charge.status != PaymentStatus.CONFIRMED:
            raise ValueError(f"payment is not confirmed: {charge.status.value}")
        if charge.amount_cents != license_record.price_cents:
            raise ValueError("payment amount does not match the license price snapshot")
        if license_record.revoked_at is not None:
            raise ValueError("cannot activate a revoked license")
        current = _utc(now)
        duration = license_record.expires_at - license_record.starts_at
        if duration <= timedelta(0):
            raise ValueError("license duration must be positive")
        start = max(license_record.expires_at, current)
        activated = replace(license_record, expires_at=start + duration)
        self.license_repository.save(activated)
        self.repository.save(replace(charge, status=PaymentStatus.SETTLED))
        return activated


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
