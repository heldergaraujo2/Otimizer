from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.auth import AuthenticationService
from otimizer_api.licensing import Entitlements, InMemoryLicenseRepository, License, LicenseAuthorizer
from otimizer_api.main import create_app
from otimizer_api.payments import InMemoryPaymentRepository, PaymentService, SandboxPixGateway


def make_auth():
    accounts = InMemoryAccountRepository([
        Account("acct-1", "user@example.com", hash_password("a-strong-development-password")),
        Account("acct-2", "other@example.com", hash_password("another-strong-password")),
    ])
    return AuthenticationService(accounts, InMemorySessionRepository())


def make_app():
    now = datetime.now(timezone.utc)
    licenses = InMemoryLicenseRepository([
        License("lic-1", "acct-1", now - timedelta(days=1), now + timedelta(days=29), Entitlements(), price_cents=2990),
        License("lic-2", "acct-2", now - timedelta(days=1), now + timedelta(days=29), Entitlements(), price_cents=3990),
    ])
    payments = InMemoryPaymentRepository()
    gateway = SandboxPixGateway(payments)
    payment_service = PaymentService(payments, gateway, licenses)
    auth = make_auth()
    app = create_app(
        license_authorizer=LicenseAuthorizer(licenses),
        auth_service=auth,
        payment_service=payment_service,
    )
    return app, payments


def bearer_headers(client, email="user@example.com", password="a-strong-development-password"):
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authenticated_user_can_create_pix_charge_for_own_license():
    client = TestClient(make_app()[0])
    response = client.post("/payments/pix", headers=bearer_headers(client), json={"license_id": "lic-1"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["license_id"] == "lic-1"
    assert payload["amount_cents"] == 2990
    assert payload["status"] == "pending"
    assert payload["pix_copy_paste"].startswith("otimizer-sandbox-pix:")


def test_authenticated_user_cannot_create_charge_for_another_account_license():
    client = TestClient(make_app()[0])
    response = client.post("/payments/pix", headers=bearer_headers(client), json={"license_id": "lic-2"})
    assert response.status_code == 404
    assert response.json()["detail"] == "License not found"


def test_authenticated_user_can_read_only_own_payment():
    app, payments = make_app()
    client = TestClient(app)
    headers = bearer_headers(client)
    created = client.post("/payments/pix", headers=headers, json={"license_id": "lic-1"})
    payment_id = created.json()["payment_id"]

    response = client.get(f"/payments/pix/{payment_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["payment_id"] == payment_id


def test_payment_endpoint_requires_authentication():
    client = TestClient(make_app()[0])
    response = client.post("/payments/pix", json={"license_id": "lic-1"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication is required"
