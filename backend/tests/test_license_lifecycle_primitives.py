from datetime import datetime, timedelta, timezone

import pytest

from otimizer_api.licensing import (
    Entitlements,
    License,
    LicenseEvent,
    LicenseStatus,
    create_license_event,
    generate_license_key,
)

NOW = datetime(2026, 9, 17, 12, 0, tzinfo=timezone.utc)


def make_license(**changes):
    values = {
        "license_id": "lic-1",
        "account_id": "acct-1",
        "starts_at": NOW,
        "expires_at": NOW + timedelta(days=30),
    }
    values.update(changes)
    return License(**values)


def test_generated_keys_are_non_empty_and_unpredictable_length():
    first = generate_license_key()
    second = generate_license_key()
    assert first
    assert second
    assert first != second
    assert len(first) >= 32


def test_license_defaults_to_active_for_backward_compatibility():
    license_record = make_license()
    assert license_record.status == LicenseStatus.ACTIVE
    assert license_record.is_active(NOW + timedelta(seconds=1))


def test_effective_status_expires_using_server_time():
    license_record = make_license()
    assert license_record.effective_status(NOW + timedelta(days=30)) == LicenseStatus.EXPIRED


def test_suspended_license_is_not_active():
    license_record = make_license(status=LicenseStatus.SUSPENDED)
    assert license_record.effective_status(NOW + timedelta(days=1)) == LicenseStatus.SUSPENDED
    assert not license_record.is_active(NOW + timedelta(days=1))


def test_revoked_license_requires_revocation_timestamp():
    with pytest.raises(ValueError):
        make_license(status=LicenseStatus.REVOKED)


def test_entitlement_limits_must_be_positive():
    with pytest.raises(ValueError):
        Entitlements(max_devices=0)
    with pytest.raises(ValueError):
        Entitlements(max_routes_per_day=0)


def test_license_event_is_immutable_audit_record():
    event = create_license_event(
        "lic-1",
        "SUSPEND",
        NOW,
        actor_account_id="admin-1",
        previous_status=LicenseStatus.ACTIVE,
        new_status=LicenseStatus.SUSPENDED,
        reason="non-payment",
    )
    assert isinstance(event, LicenseEvent)
    assert event.license_id == "lic-1"
    assert event.actor_account_id == "admin-1"
    assert event.previous_status == LicenseStatus.ACTIVE
    assert event.new_status == LicenseStatus.SUSPENDED
    assert event.reason == "non-payment"
