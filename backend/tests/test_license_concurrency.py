from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

from otimizer_api.accounts import Account, AccountRole, hash_password
from otimizer_api.licensing import Entitlements, License, LicenseConcurrencyError, LicenseLifecycleService, LicenseStatus
from otimizer_api.persistence import SQLiteAccountRepository, SQLiteDatabase, SQLiteLicenseEventRepository, SQLiteLicenseRepository

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def setup(tmp_path, status=LicenseStatus.ACTIVE):
    database = SQLiteDatabase(tmp_path / "concurrency.db")
    accounts = SQLiteAccountRepository(database)
    accounts.save(Account("acct-1", "admin@example.test", hash_password("Strong-password-123"), role=AccountRole.ADMIN))
    licenses = SQLiteLicenseRepository(database)
    licenses.save(License("lic-concurrent", "acct-1", NOW, NOW + timedelta(days=30), Entitlements(), status=status))
    events = SQLiteLicenseEventRepository(database)
    return licenses, events


class ReadBarrierRepository:
    def __init__(self, repository, barrier):
        self.repository = repository
        self.barrier = barrier
    def get_by_id(self, license_id):
        record = self.repository.get_by_id(license_id)
        self.barrier.wait(timeout=10)
        return record
    def save_with_event(self, license_record, event):
        return self.repository.save_with_event(license_record, event)


def run_two(licenses, events, operation):
    barrier = Barrier(2)
    def invoke():
        repository = ReadBarrierRepository(licenses, barrier)
        return operation(LicenseLifecycleService(repository, events))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(invoke) for _ in range(2)]
        results = []
        for future in futures:
            try:
                results.append(("ok", future.result()))
            except Exception as exc:
                results.append(("error", exc))
        return results


def assert_one_success(results):
    assert sum(kind == "ok" for kind, _ in results) == 1
    assert sum(isinstance(value, LicenseConcurrencyError) for kind, value in results if kind == "error") == 1


def test_concurrent_activation_has_single_winner_and_event(tmp_path):
    licenses, events = setup(tmp_path, LicenseStatus.AVAILABLE)
    results = run_two(licenses, events, lambda service: service.activate("lic-concurrent", "acct-1", NOW))
    assert_one_success(results)
    assert licenses.get_by_id("lic-concurrent").status is LicenseStatus.ACTIVE
    history = events.list_for_license("lic-concurrent")
    assert len(history) == 1
    assert history[0].action == "ACTIVATED"


def test_concurrent_revocation_has_single_winner_and_event(tmp_path):
    licenses, events = setup(tmp_path)
    results = run_two(licenses, events, lambda service: service.revoke("lic-concurrent", "acct-1", "concurrent security test", NOW))
    assert_one_success(results)
    assert licenses.get_by_id("lic-concurrent").status is LicenseStatus.REVOKED
    history = events.list_for_license("lic-concurrent")
    assert len(history) == 1
    assert history[0].action == "REVOKED"


def test_concurrent_renewal_cannot_lose_update(tmp_path):
    licenses, events = setup(tmp_path)
    results = run_two(licenses, events, lambda service: service.renew("lic-concurrent", "acct-1", timedelta(days=30), NOW))
    assert_one_success(results)
    stored = licenses.get_by_id("lic-concurrent")
    assert stored.renewal_count == 1
    assert stored.expires_at == NOW + timedelta(days=60)
    history = events.list_for_license("lic-concurrent")
    assert len(history) == 1
    assert history[0].action == "RENEWED"
