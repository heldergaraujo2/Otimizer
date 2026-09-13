from datetime import timedelta

import pytest

from otimizer_api.payments import InMemoryPaymentRepository, PaymentStatus, SandboxPixGateway


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
