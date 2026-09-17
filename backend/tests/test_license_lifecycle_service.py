from datetime import datetime, timedelta, timezone
import pytest

from otimizer_api.licensing import (
    Entitlements, InMemoryLicenseEventRepository, InMemoryLicenseRepository,
    License, LicenseLifecycleError, LicenseLifecycleService, LicenseStatus,
)

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def make_service(status=LicenseStatus.AVAILABLE, expires=NOW + timedelta(days=30)):
    license_record = License("lic-1", "acct-1", NOW, expires, Entitlements(max_devices=2), status=status)
    repository = InMemoryLicenseRepository([license_record])
    events = InMemoryLicenseEventRepository()
    return LicenseLifecycleService(repository, events), repository, events


def test_activation_records_server_time_and_event():
    service, repository, events = make_service()
    activated = service.activate("lic-1", "admin-1", NOW)
    assert activated.status is LicenseStatus.ACTIVE
    assert activated.activated_at == NOW
    assert events.list_for_license("lic-1")[-1].action == "ACTIVATED"


def test_activation_is_not_allowed_twice():
    service, _, _ = make_service(status=LicenseStatus.ACTIVE)
    with pytest.raises(LicenseLifecycleError):
        service.activate("lic-1", "admin-1", NOW)


def test_suspend_requires_reason_and_reactivation_requires_validity():
    service, repository, _ = make_service(status=LicenseStatus.ACTIVE)
    suspended = service.suspend("lic-1", "admin-1", "inadimplencia", NOW)
    assert suspended.status is LicenseStatus.SUSPENDED
    reactivated = service.reactivate("lic-1", "admin-1", NOW + timedelta(days=1))
    assert reactivated.status is LicenseStatus.ACTIVE
    assert reactivated.activated_at is None
    assert repository.get_by_id("lic-1").status is LicenseStatus.ACTIVE


def test_revocation_is_permanent():
    service, _, events = make_service(status=LicenseStatus.ACTIVE)
    revoked = service.revoke("lic-1", "admin-1", "fraude", NOW)
    assert revoked.status is LicenseStatus.REVOKED
    with pytest.raises(LicenseLifecycleError):
        service.reactivate("lic-1", "admin-1", NOW)
    with pytest.raises(LicenseLifecycleError):
        service.revoke("lic-1", "admin-1", "novo motivo", NOW)
    assert events.list_for_license("lic-1")[-1].new_status is LicenseStatus.REVOKED


def test_expiration_is_server_time_driven_and_idempotent():
    service, repository, events = make_service(status=LicenseStatus.ACTIVE, expires=NOW + timedelta(days=1))
    with pytest.raises(LicenseLifecycleError):
        service.expire("lic-1", NOW)
    expired = service.expire("lic-1", NOW + timedelta(days=1))
    assert expired.status is LicenseStatus.EXPIRED
    same = service.expire("lic-1", NOW + timedelta(days=2))
    assert same == expired
    assert [event.action for event in events.list_for_license("lic-1")] == ["EXPIRED"]
    assert repository.get_by_id("lic-1").effective_status(NOW + timedelta(days=2)) is LicenseStatus.EXPIRED


def test_renewal_extends_from_later_of_expiration_and_server_now():
    service, repository, events = make_service(status=LicenseStatus.EXPIRED, expires=NOW - timedelta(days=2))
    renewed = service.renew("lic-1", "admin-1", timedelta(days=30), NOW)
    assert renewed.status is LicenseStatus.ACTIVE
    assert renewed.expires_at == NOW + timedelta(days=30)
    assert renewed.renewal_count == 1
    assert renewed.last_renewal_at == NOW
    assert events.list_for_license("lic-1")[-1].action == "RENEWED"
    assert repository.get_by_id("lic-1") == renewed


def test_suspended_license_cannot_be_renewed():
    service, _, _ = make_service(status=LicenseStatus.SUSPENDED)
    with pytest.raises(LicenseLifecycleError):
        service.renew("lic-1", "admin-1", timedelta(days=30), NOW)


def test_expired_license_cannot_be_activated_directly():
    service, _, _ = make_service(status=LicenseStatus.AVAILABLE, expires=NOW - timedelta(seconds=1))
    with pytest.raises(LicenseLifecycleError):
        service.activate("lic-1", "admin-1", NOW)


def test_renewal_duration_must_be_positive():
    service, _, _ = make_service(status=LicenseStatus.ACTIVE)
    with pytest.raises(LicenseLifecycleError):
        service.renew("lic-1", "admin-1", timedelta(0), NOW)
