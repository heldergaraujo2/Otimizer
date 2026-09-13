from datetime import datetime, timedelta, timezone

from otimizer_api.licensing import Entitlements, InMemoryLicenseRepository, License, LicenseAuthorizer


NOW = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)


def make_license(**kwargs):
    values = {
        "license_id": "lic-1",
        "account_id": "acct-1",
        "starts_at": NOW - timedelta(days=1),
        "expires_at": NOW + timedelta(days=30),
    }
    values.update(kwargs)
    return License(**values)


def test_active_license_authorizes_route():
    authorizer = LicenseAuthorizer(InMemoryLicenseRepository([make_license()]))
    decision = authorizer.authorize_route("acct-1", NOW)
    assert decision.allowed is True
    assert decision.code == "AUTHORIZED"


def test_expired_license_denies_route():
    license_record = make_license(expires_at=NOW)
    authorizer = LicenseAuthorizer(InMemoryLicenseRepository([license_record]))
    decision = authorizer.authorize_route("acct-1", NOW)
    assert decision.allowed is False
    assert decision.code == "LICENSE_REQUIRED"


def test_revoked_license_denies_route():
    license_record = make_license(revoked_at=NOW - timedelta(hours=1))
    authorizer = LicenseAuthorizer(InMemoryLicenseRepository([license_record]))
    decision = authorizer.authorize_route("acct-1", NOW)
    assert decision.allowed is False
    assert decision.code == "LICENSE_REQUIRED"


def test_plan_without_route_entitlement_denies_route():
    license_record = make_license(entitlements=Entitlements(route_optimization=False))
    authorizer = LicenseAuthorizer(InMemoryLicenseRepository([license_record]))
    decision = authorizer.authorize_route("acct-1", NOW)
    assert decision.allowed is False
    assert decision.code == "FEATURE_NOT_ENTITLED"


def test_repository_selects_latest_expiring_active_license():
    first = make_license(license_id="lic-1", expires_at=NOW + timedelta(days=5))
    second = make_license(license_id="lic-2", expires_at=NOW + timedelta(days=20))
    repository = InMemoryLicenseRepository([first, second])
    assert repository.get_active_license("acct-1", NOW).license_id == "lic-2"
