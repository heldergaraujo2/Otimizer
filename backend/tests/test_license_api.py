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
        price_cents=2990,
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
    client = TestClient(create_app(license_authorizer=authorizer_for()))
    response = client.post("/optimize", files={"file": ("x.xlsx", b"bad", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert response.status_code == 401


def test_license_status_requires_authentication():
    client = TestClient(create_app(license_authorizer=authorizer_for(), auth_service=auth_service()))

    response = client.get("/licenses/me")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication is required"


def test_license_status_returns_own_license():
    client = TestClient(create_app(license_authorizer=authorizer_for(), auth_service=auth_service()))
    response = client.get("/licenses/me", headers=bearer_headers(client))
    assert response.status_code == 200
    payload = response.json()
    assert payload["active"] is True
    assert payload["license"]["license_id"] == "lic-1"
    assert payload["license"]["account_id"] == "acct-1"
    assert payload["license"]["price_cents"] == 2990
    assert payload["license"]["entitlements"]["route_optimization"] is True
