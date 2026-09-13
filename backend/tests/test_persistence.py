from datetime import datetime, timedelta, timezone

from otimizer_api.accounts import Account, Session
from otimizer_api.licensing import Entitlements, License
from otimizer_api.payments import PaymentStatus, PixCharge
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
