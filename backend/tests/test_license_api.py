from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.auth import AuthenticationService
from otimizer_api.licensing import InMemoryLicenseRepository, License, LicenseAuthorizer
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        from otimizer_importer.routing import TravelMetric

        size = len(locations)
        return tuple(
            tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size))
            for row in range(size)
        )


def authorizer_for(*, active=True):
    now = datetime.now(timezone.utc)
    license_record = License(
        license_id="lic-1",
        account_id="acct-1",
        starts_at=now - timedelta(days=1),
        expires_at=now + timedelta(days=1) if active else now - timedelta(seconds=1),
    )
    return LicenseAuthorizer(InMemoryLicenseRepository([license_record]))


def auth_service():
    accounts = InMemoryAccountRepository([
        Account("acct-1", "user@example.com", hash_password("a-strong-development-password")),
    ])
    return AuthenticationService(accounts, InMemorySessionRepository())


def bearer_headers(client):
    response = client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "a-strong-development-password"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_protected_route_requires_account_identity():
    client = TestClient(create_app(FakeRoutingProvider(), authorizer_for()))
    response = client.post(
        "/optimize",
        files={
            "file": (
                "route.xlsx",
                b"placeholder",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication is required"


def test_protected_route_denies_expired_license_before_processing_upload():
    client = TestClient(create_app(FakeRoutingProvider(), authorizer_for(active=False)))
    response = client.post(
        "/optimize",
        headers={"X-Otimizer-Account-ID": "acct-1"},
        files={"file": ("bad.txt", b"not processed", "text/plain")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LICENSE_REQUIRED"


def test_bearer_authentication_controls_license_check():
    client = TestClient(create_app(
        FakeRoutingProvider(),
        authorizer_for(active=False),
        auth_service(),
    ))
    response = client.post(
        "/optimize",
        headers=bearer_headers(client),
        files={"file": ("bad.txt", b"not processed", "text/plain")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LICENSE_REQUIRED"


def test_active_license_allows_request_to_reach_file_validation():
    client = TestClient(create_app(
        FakeRoutingProvider(),
        authorizer_for(active=True),
        auth_service(),
    ))
    response = client.post(
        "/optimize",
        headers=bearer_headers(client),
        files={"file": ("bad.txt", b"not processed", "text/plain")},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "The uploaded file must be an .xlsx workbook"
