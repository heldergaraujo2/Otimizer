from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.licensing import Entitlements, InMemoryLicenseRepository, License
from otimizer_api.payments import InMemoryPaymentRepository, PaymentService, PaymentStatus, SandboxPixGateway


def make_license(price_cents: int = 2990) -> License:
    starts = datetime.now(timezone.utc)
    return License("lic-1", "account-1", starts, starts + timedelta(days=30), Entitlements(), price_cents=price_cents)


def test_sandbox_pix_charge_is_created_and_confirmed_idempotently() -> None:
    repository = InMemoryPaymentRepository()
    gateway = SandboxPixGateway(repository)
    charge = gateway.create_charge("account-1", "license-1", 1990, timedelta(minutes=10))
    assert charge.status is PaymentStatus.PENDING
    confirmed = gateway.confirm_sandbox_charge(charge.payment_id)
    assert confirmed.status is PaymentStatus.CONFIRMED
    assert gateway.confirm_sandbox_charge(charge.payment_id) == confirmed


def test_payment_service_uses_server_license_price_and_snapshots_amount() -> None:
    repository = InMemoryPaymentRepository()
    service = PaymentService(repository, SandboxPixGateway(repository))
    license_record = make_license(2990)
    charge = service.create_license_charge(license_record)
    assert charge.license_id == "lic-1"
    assert charge.amount_cents == 2990
    assert license_record.change_price(4990).price_cents == 4990
    assert repository.get(charge.payment_id) == charge


def test_payment_service_settles_confirmed_payment_once() -> None:
    payments = InMemoryPaymentRepository()
    licenses = InMemoryLicenseRepository([make_license()])
    gateway = SandboxPixGateway(payments)
    service = PaymentService(payments, gateway, licenses)
    license_record = licenses.get_by_id("lic-1")
    assert license_record is not None
    charge = service.create_license_charge(license_record)
    gateway.confirm_sandbox_charge(charge.payment_id)
    now = datetime.now(timezone.utc)

    activated = service.settle_confirmed_payment(charge.payment_id, now=now)
    again = service.settle_confirmed_payment(charge.payment_id, now=now + timedelta(hours=1))

    assert activated.expires_at > now + timedelta(days=29)
    assert again == activated
    stored_charge = payments.get(charge.payment_id)
    assert stored_charge is not None
    assert stored_charge.status is PaymentStatus.SETTLED


def test_payment_service_rejects_unconfirmed_payment() -> None:
    payments = InMemoryPaymentRepository()
    licenses = InMemoryLicenseRepository([make_license()])
    service = PaymentService(payments, SandboxPixGateway(payments), licenses)
    license_record = licenses.get_by_id("lic-1")
    assert license_record is not None
    charge = service.create_license_charge(license_record)
    payments.save(charge.__class__(**{**charge.__dict__, "status": PaymentStatus.FAILED}))
    with pytest.raises(ValueError, match="not confirmed"):
        service.settle_confirmed_payment(charge.payment_id)


def test_payment_service_accepts_existing_charge_after_license_price_change() -> None:
    payments = InMemoryPaymentRepository()
    licenses = InMemoryLicenseRepository([make_license(2990)])
    gateway = SandboxPixGateway(payments)
    service = PaymentService(payments, gateway, licenses)
    license_record = licenses.get_by_id("lic-1")
    assert license_record is not None
    charge = service.create_license_charge(license_record)
    gateway.confirm_sandbox_charge(charge.payment_id)
    licenses.save(license_record.change_price(4990))

    activated = service.settle_confirmed_payment(charge.payment_id)

    assert activated.price_cents == 4990
    assert activated.expires_at > activated.starts_at
    assert payments.get(charge.payment_id) is not None
    assert payments.get(charge.payment_id).status is PaymentStatus.SETTLED


def test_payment_service_rejects_free_license() -> None:
    repository = InMemoryPaymentRepository()
    service = PaymentService(repository, SandboxPixGateway(repository))
    with pytest.raises(ValueError):
        service.create_license_charge(make_license(0))


def test_sandbox_pix_rejects_invalid_amount_and_expiration() -> None:
    gateway = SandboxPixGateway(InMemoryPaymentRepository())
    with pytest.raises(ValueError):
        gateway.create_charge("account-1", "license-1", 0, timedelta(minutes=10))
    with pytest.raises(ValueError):
        gateway.create_charge("account-1", "license-1", 1000, timedelta(0))


def test_sandbox_pix_missing_payment_is_rejected() -> None:
    gateway = SandboxPixGateway(InMemoryPaymentRepository())
    with pytest.raises(KeyError):
        gateway.confirm_sandbox_charge("missing")
