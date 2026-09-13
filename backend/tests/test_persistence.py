from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.accounts import Account, Session
from otimizer_api.licensing import Entitlements, License
from otimizer_api.payments import PaymentService, PaymentStatus, PixCharge, SandboxPixGateway
from otimizer_api.persistence import (
    SQLiteAccountRepository,
    SQLiteDatabase,
    SQLiteLicenseRepository,
    SQLitePaymentRepository,
    SQLiteSessionRepository,
)


def test_account_repository_persists_across_repository_instances(tmp_path):
    database = SQLiteDatabase(tmp_path / "otimizer.db")
    account = Account("acct-1", "USER@EXAMPLE.COM", "argon2-hash")
    SQLiteAccountRepository(database).save(account)
    restored = SQLiteAccountRepository(database).get_by_email(" user@example.com ")
    assert restored == Account("acct-1", "user@example.com", "argon2-hash", True)
    assert SQLiteAccountRepository(database).get_by_id("acct-1") == restored


def test_session_repository_persists_and_revoke_is_durable(tmp_path):
    database = SQLiteDatabase(tmp_path / "otimizer.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    session = Session("session-1", "acct-1", "token-hash", datetime.now(timezone.utc) + timedelta(hours=1))
    SQLiteSessionRepository(database).save(session)
    restored = SQLiteSessionRepository(database).get_by_token_hash("token-hash")
    assert restored == session
    revoked_at = datetime.now(timezone.utc)
    SQLiteSessionRepository(database).revoke("session-1", revoked_at)
    revoked = SQLiteSessionRepository(database).get_by_token_hash("token-hash")
    assert revoked is not None
    assert revoked.revoked_at is not None
    assert not revoked.is_active(revoked_at + timedelta(seconds=1))


def test_license_repository_returns_latest_active_license(tmp_path):
    database = SQLiteDatabase(tmp_path / "otimizer.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    repository = SQLiteLicenseRepository(database)
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    repository.save(License("license-old", "acct-1", now - timedelta(days=10), now + timedelta(days=5)))
    latest = License("license-latest", "acct-1", now - timedelta(days=1), now + timedelta(days=30), Entitlements(max_devices=3, max_routes_per_day=50))
    repository.save(latest)
    repository.save(License("license-future", "acct-1", now + timedelta(days=1), now + timedelta(days=40)))
    assert repository.get_active_license("acct-1", now) == latest


def test_license_repository_does_not_return_revoked_or_expired_license(tmp_path):
    database = SQLiteDatabase(tmp_path / "otimizer.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    repository = SQLiteLicenseRepository(database)
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)
    repository.save(License("license-revoked", "acct-1", now - timedelta(days=2), now + timedelta(days=2), revoked_at=now - timedelta(hours=1)))
    repository.save(License("license-expired", "acct-1", now - timedelta(days=4), now - timedelta(days=1)))
    assert repository.get_active_license("acct-1", now) is None


def test_payment_repository_persists_amount_status_and_license_binding(tmp_path):
    database = SQLiteDatabase(tmp_path / "otimizer.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    license_record = License("license-1", "acct-1", datetime(2026, 9, 1, tzinfo=timezone.utc), datetime(2026, 10, 1, tzinfo=timezone.utc), price_cents=2990)
    SQLiteLicenseRepository(database).save(license_record)
    repository = SQLitePaymentRepository(database)
    charge = PixCharge("payment-1", "acct-1", "license-1", 2990, datetime(2026, 9, 13, 13, tzinfo=timezone.utc), "otimizer-sandbox-pix:payment-1")
    repository.save(charge)
    assert repository.get("payment-1") == charge
    settled = PixCharge(**{**charge.__dict__, "status": PaymentStatus.SETTLED})
    repository.save(settled)
    assert repository.get("payment-1") == settled


def _seed_sqlite_payment(tmp_path, price_cents=2990):
    database = SQLiteDatabase(tmp_path / "settlement.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    starts = datetime(2026, 9, 1, tzinfo=timezone.utc)
    license_record = License("license-1", "acct-1", starts, starts + timedelta(days=30), price_cents=price_cents)
    licenses = SQLiteLicenseRepository(database)
    licenses.save(license_record)
    payments = SQLitePaymentRepository(database)
    gateway = SandboxPixGateway(payments)
    service = PaymentService(payments, gateway, licenses)
    return database, licenses, payments, gateway, service, license_record


def test_sqlite_settlement_updates_payment_and_license_atomically(tmp_path):
    _, licenses, payments, gateway, service, license_record = _seed_sqlite_payment(tmp_path)
    charge = service.create_license_charge(license_record)
    gateway.confirm_sandbox_charge(charge.payment_id)
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)

    activated = service.settle_confirmed_payment(charge.payment_id, now=now)

    assert activated.expires_at == now + timedelta(days=30)
    assert licenses.get_by_id("license-1") == activated
    settled = payments.get(charge.payment_id)
    assert settled is not None
    assert settled.status is PaymentStatus.SETTLED


def test_sqlite_settlement_is_idempotent_and_does_not_extend_twice(tmp_path):
    _, licenses, payments, gateway, service, license_record = _seed_sqlite_payment(tmp_path)
    charge = service.create_license_charge(license_record)
    gateway.confirm_sandbox_charge(charge.payment_id)
    now = datetime(2026, 9, 13, 12, tzinfo=timezone.utc)

    first = service.settle_confirmed_payment(charge.payment_id, now=now)
    second = service.settle_confirmed_payment(charge.payment_id, now=now + timedelta(days=1))

    assert second == first
    assert licenses.get_by_id("license-1") == first
    assert payments.get(charge.payment_id).status is PaymentStatus.SETTLED


def test_sqlite_settlement_uses_charge_price_snapshot_after_license_price_change(tmp_path):
    _, licenses, payments, gateway, service, license_record = _seed_sqlite_payment(tmp_path, 2990)
    charge = service.create_license_charge(license_record)
    gateway.confirm_sandbox_charge(charge.payment_id)
    licenses.save(license_record.change_price(4990))

    activated = service.settle_confirmed_payment(charge.payment_id, now=datetime(2026, 9, 13, 12, tzinfo=timezone.utc))

    assert activated.price_cents == 4990
    assert payments.get(charge.payment_id).status is PaymentStatus.SETTLED


def test_sqlite_settlement_rejects_unconfirmed_payment(tmp_path):
    _, _, _, _, service, license_record = _seed_sqlite_payment(tmp_path)
    charge = service.create_license_charge(license_record)
    with pytest.raises(ValueError, match="not confirmed"):
        service.settle_confirmed_payment(charge.payment_id)
