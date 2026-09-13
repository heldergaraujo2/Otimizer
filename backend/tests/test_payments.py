from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.licensing import Entitlements, License
from otimizer_api.payments import InMemoryPaymentRepository, PaymentService, PaymentStatus, SandboxPixGateway


def make_license(price_cents: int = 2990) -> License:
    starts = datetime.now(timezone.utc)
    return License(
        license_id="lic-1",
        account_id="account-1",
        starts_at=starts,
        expires_at=starts + timedelta(days=30),
        entitlements=Entitlements(),
        price_cents=price_cents,
    )


def test_sandbox_pix_charge_is_created_and_confirmed_idempotently() -> None:
    repository = InMemoryPaymentRepository()
    gateway = SandboxPixGateway(repository)

    charge = gateway.create_charge("account-1", 1990, timedelta(minutes=10))
    assert charge.status is PaymentStatus.PENDING
    assert charge.amount_cents == 1990
    assert charge.pix_copy_paste.startswith("otimizer-sandbox-pix:")

    confirmed = gateway.confirm_sandbox_charge(charge.payment_id)
    assert confirmed.status is PaymentStatus.CONFIRMED
    assert gateway.confirm_sandbox_charge(charge.payment_id) == confirmed


def test_payment_service_uses_server_license_price_and_snapshots_amount() -> None:
    repository = InMemoryPaymentRepository()
    gateway = SandboxPixGateway(repository)
    service = PaymentService(repository, gateway)
    license_record = make_license(2990)

    charge = service.create_license_charge(license_record)
    changed_license = license_record.change_price(4990)

    assert charge.license_id == "lic-1"
    assert charge.account_id == "account-1"
    assert charge.amount_cents == 2990
    assert changed_license.price_cents == 4990
    assert repository.get(charge.payment_id) == charge


def test_payment_service_rejects_free_license() -> None:
    repository = InMemoryPaymentRepository()
    service = PaymentService(repository, SandboxPixGateway(repository))

    with pytest.raises(ValueError):
        service.create_license_charge(make_license(0))


def test_sandbox_pix_rejects_invalid_amount_and_expiration() -> None:
    gateway = SandboxPixGateway(InMemoryPaymentRepository())

    with pytest.raises(ValueError):
        gateway.create_charge("account-1", 0, timedelta(minutes=10))

    with pytest.raises(ValueError):
        gateway.create_charge("account-1", 1000, timedelta(0))


def test_sandbox_pix_missing_payment_is_rejected() -> None:
    gateway = SandboxPixGateway(InMemoryPaymentRepository())

    with pytest.raises(KeyError):
        gateway.confirm_sandbox_charge("missing")
