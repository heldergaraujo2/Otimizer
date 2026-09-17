from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256

from otimizer_api.accounts import Account, AccountRole, InMemorySessionRepository, Session, authenticate_session, hash_password
from otimizer_api.devices import Device, SQLiteDeviceRepository, hash_device_secret
from otimizer_api.licensing import (
    Entitlements,
    InMemoryLicenseEventRepository,
    InMemoryLicenseRepository,
    License,
    LicenseLifecycleError,
    LicenseLifecycleService,
    LicenseStatus,
)
from otimizer_api.persistence import SQLiteAccountRepository, SQLiteDatabase, SQLiteLicenseRepository

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def make_license(status=LicenseStatus.ACTIVE, *, account_id="acct-1", expires=NOW + timedelta(days=30), max_devices=1):
    revoked_at = NOW if status is LicenseStatus.REVOKED else None
    return License(
        license_id="lic-1",
        account_id=account_id,
        starts_at=NOW,
        expires_at=expires,
        entitlements=Entitlements(max_devices=max_devices),
        status=status,
        revoked_at=revoked_at,
    )


def test_license_key_is_not_derived_from_license_id():
    first = make_license()
    second = License("lic-2", "acct-1", NOW, NOW + timedelta(days=30))
    assert first.license_key != first.license_id
    assert second.license_key != second.license_id
    assert first.license_key != second.license_key


def test_tampering_with_key_does_not_change_authoritative_license_state():
    record = make_license(status=LicenseStatus.ACTIVE)
    repository = InMemoryLicenseRepository([record])
    events = InMemoryLicenseEventRepository()
    service = LicenseLifecycleService(repository, events)
    tampered = record.license_key[:-1] + ("A" if record.license_key[-1] != "A" else "B")
    assert tampered != record.license_key
    service.suspend("lic-1", "admin-1", "security test", NOW)
    assert repository.get_by_id("lic-1").status is LicenseStatus.SUSPENDED
    assert repository.get_by_id("lic-1").license_key == record.license_key


def test_revoke_is_terminal_even_after_expiration():
    record = make_license(status=LicenseStatus.REVOKED, expires=NOW - timedelta(seconds=1))
    repository = InMemoryLicenseRepository([record])
    service = LicenseLifecycleService(repository, InMemoryLicenseEventRepository())
    try:
        service.reactivate("lic-1", "admin-1", NOW)
    except LicenseLifecycleError:
        pass
    else:
        raise AssertionError("revoked license was reactivated")


def test_session_token_replay_fails_after_expiration():
    sessions = InMemorySessionRepository()
    token = "server-generated-test-token"
    sessions.save(Session("session-1", "acct-1", sha256(token.encode()).hexdigest(), NOW + timedelta(minutes=5)))
    assert authenticate_session(token, sessions, NOW) is not None
    assert authenticate_session(token, sessions, NOW + timedelta(minutes=5, seconds=1)) is None


def test_device_secret_is_stored_only_as_hash():
    secret = "installation-secret-very-long"
    hashed = hash_device_secret(secret)
    assert hashed != secret
    assert len(hashed) == 64


def test_sqlite_device_capacity_is_atomic_under_concurrency(tmp_path):
    database = SQLiteDatabase(tmp_path / "security.db")
    accounts = SQLiteAccountRepository(database)
    licenses = SQLiteLicenseRepository(database)
    accounts.save(Account("acct-1", "admin@example.test", hash_password("Strong-password-123"), role=AccountRole.ADMIN))
    licenses.save(make_license(max_devices=1))
    devices = SQLiteDeviceRepository(database)

    def bind(index):
        device = Device(
            f"device-{index}",
            "acct-1",
            "lic-1",
            hash_device_secret(f"secret-{index}"),
            NOW,
            NOW,
        )
        return devices.register(device, 1)[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(bind, range(8)))

    assert sum(results) == 1
    assert len(devices.list_for_license("lic-1")) == 1
