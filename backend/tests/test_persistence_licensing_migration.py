from datetime import datetime, timedelta, timezone
import sqlite3

from otimizer_api.accounts import Account, AccountRole
from otimizer_api.licensing import Entitlements, License, LicenseEvent, LicenseStatus
from otimizer_api.persistence import SQLiteAccountRepository, SQLiteDatabase, SQLiteLicenseEventRepository, SQLiteLicenseRepository


def test_account_role_is_persisted(tmp_path):
    database = SQLiteDatabase(tmp_path / "roles.db")
    repository = SQLiteAccountRepository(database)
    repository.save(Account("admin-1", "admin@example.com", "hash", role=AccountRole.ADMIN))
    assert repository.get_by_id("admin-1").role is AccountRole.ADMIN


def test_license_commercial_fields_and_key_are_persisted(tmp_path):
    database = SQLiteDatabase(tmp_path / "license.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    now = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)
    license_record = License(
        "license-1", "acct-1", now, now + timedelta(days=30),
        Entitlements(max_devices=3, max_routes_per_day=20),
        price_cents=4990, plan="professional", status=LicenseStatus.AVAILABLE,
    )
    repository = SQLiteLicenseRepository(database)
    repository.save(license_record)
    restored = repository.get_by_id("license-1")
    assert restored == license_record
    assert restored.license_key == license_record.license_key
    assert restored.plan == "professional"
    assert restored.status is LicenseStatus.AVAILABLE


def test_license_key_has_database_uniqueness_constraint(tmp_path):
    database = SQLiteDatabase(tmp_path / "unique.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    first = License("license-1", "acct-1", now, now + timedelta(days=30))
    second = License("license-2", "acct-1", now, now + timedelta(days=30), license_key=first.license_key)
    repository = SQLiteLicenseRepository(database)
    repository.save(first)
    try:
        repository.save(second)
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("duplicate license_key must be rejected by SQLite")


def test_license_events_are_durable_and_ordered(tmp_path):
    database = SQLiteDatabase(tmp_path / "events.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    license_record = License("license-1", "acct-1", now, now + timedelta(days=30))
    SQLiteLicenseRepository(database).save(license_record)
    repository = SQLiteLicenseEventRepository(database)
    repository.append(LicenseEvent("e2", "license-1", "ACTIVATED", now + timedelta(minutes=2), "acct-1", LicenseStatus.AVAILABLE, LicenseStatus.ACTIVE))
    repository.append(LicenseEvent("e1", "license-1", "GENERATED", now, "acct-1", None, LicenseStatus.GENERATED))
    events = repository.list_for_license("license-1")
    assert [event.event_id for event in events] == ["e1", "e2"]


def test_legacy_database_is_migrated_without_losing_license_data(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE accounts(account_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE licenses(license_id TEXT PRIMARY KEY, account_id TEXT NOT NULL, starts_at TEXT NOT NULL, expires_at TEXT NOT NULL, route_optimization INTEGER NOT NULL DEFAULT 1, max_devices INTEGER NOT NULL DEFAULT 1, max_routes_per_day INTEGER, price_cents INTEGER NOT NULL DEFAULT 0, revoked_at TEXT);
        """
    )
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    connection.execute("INSERT INTO accounts VALUES (?, ?, ?, ?)", ("acct-1", "user@example.com", "hash", 1))
    connection.execute("INSERT INTO licenses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", ("legacy-1", "acct-1", now.isoformat(), (now + timedelta(days=30)).isoformat(), 1, 1, None, 2990, None))
    connection.commit()
    connection.close()

    database = SQLiteDatabase(path)
    account = SQLiteAccountRepository(database).get_by_id("acct-1")
    license_record = SQLiteLicenseRepository(database).get_by_id("legacy-1")
    assert account is not None and account.role is AccountRole.USER
    assert license_record is not None
    assert license_record.license_id == "legacy-1"
    assert license_record.price_cents == 2990
    assert license_record.license_key
    assert license_record.status is LicenseStatus.ACTIVE
