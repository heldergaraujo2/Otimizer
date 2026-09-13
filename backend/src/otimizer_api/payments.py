"""Provider-neutral Pix payment domain with a deterministic sandbox gateway.

The gateway intentionally does not move real money. Production providers can
implement the same protocol later; payment confirmation must come from the
provider/backend webhook, never from the browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Protocol
from uuid import uuid4


class PaymentStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"
    FAILED = "failed"


@dataclass(frozen=True)
class PixCharge:
    payment_id: str
    account_id: str
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
    def create_charge(self, account_id: str, amount_cents: int, expires_in: timedelta) -> PixCharge: ...

    def confirm_sandbox_charge(self, payment_id: str) -> PixCharge: ...


class SandboxPixGateway:
    """Fake Pix gateway used for automated and manual end-to-end tests."""

    def __init__(self, repository: PaymentRepository) -> None:
        self.repository = repository

    def create_charge(self, account_id: str, amount_cents: int, expires_in: timedelta) -> PixCharge:
        if amount_cents <= 0:
            raise ValueError("amount_cents must be positive")
        if expires_in <= timedelta(0):
            raise ValueError("expires_in must be positive")
        now = datetime.now(timezone.utc)
        payment_id = str(uuid4())
        charge = PixCharge(
            payment_id=payment_id,
            account_id=account_id,
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
            expired = PixCharge(**{**charge.__dict__, "status": PaymentStatus.EXPIRED})
            self.repository.save(expired)
            return expired
        confirmed = PixCharge(**{**charge.__dict__, "status": PaymentStatus.CONFIRMED})
        self.repository.save(confirmed)
        return confirmed
