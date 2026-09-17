from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.accounts import Account, AccountRole, hash_password
from otimizer_api.licensing import Entitlements, License, LicenseEvent, LicenseLifecycleService, LicenseStatus
from otimizer_api.persistence import SQLiteAccountRepository, SQLiteDatabase, SQLiteLicenseEventRepository, SQLiteLicenseRepository

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def _license():
    return License("lic-atomic", "acct-1", NOW, NOW + timedelta(days=30), Entitlements(max_devices=1), status=LicenseStatus.AVAILABLE)


def test_license_transition_rolls_back_when_audit_insert_fails(tmp_path):
    database = SQLiteDatabase(tmp_path / "atomic.db")
    accounts = SQLiteAccountRepository(database)
    accounts.save(Account("acct-1", "admin@example.test", hash_password("Strong-password-123"), role=AccountRole.ADMIN))
    licenses = SQLiteLicenseRepository(database)
    licenses.save(_license())
    events = SQLiteLicenseEventRepository(database)
    service = LicenseLifecycleService(licenses, events)

    with pytest.raises(Exception):
        service.activate("lic-atomic", "missing-admin", NOW)

    stored = licenses.get_by_id("lic-atomic")
    assert stored is not None
    assert stored.status is LicenseStatus.AVAILABLE
    assert events.list_for_license("lic-atomic") == []


def test_atomic_repository_commits_license_and_event_together(tmp_path):
    database = SQLiteDatabase(tmp_path / "atomic-success.db")
    accounts = SQLiteAccountRepository(database)
    accounts.save(Account("acct-1", "admin@example.test", hash_password("Strong-password-123"), role=AccountRole.ADMIN))
    licenses = SQLiteLicenseRepository(database)
    licenses.save(_license())
    events = SQLiteLicenseEventRepository(database)
    service = LicenseLifecycleService(licenses, events)

    activated = service.activate("lic-atomic", "acct-1", NOW)
    assert activated.status is LicenseStatus.ACTIVE
    stored = licenses.get_by_id("lic-atomic")
    history = events.list_for_license("lic-atomic")
    assert stored is not None and stored.status is LicenseStatus.ACTIVE
    assert len(history) == 1
    assert history[0].new_status is LicenseStatus.ACTIVE
