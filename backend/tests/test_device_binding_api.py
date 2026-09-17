from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, AccountRole, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.admin_api import register_admin_routes
from otimizer_api.auth import AuthenticationService
from otimizer_api.devices import InMemoryDeviceRepository
from otimizer_api.licensing import Entitlements, InMemoryLicenseEventRepository, InMemoryLicenseRepository, License, LicenseStatus, LicenseLifecycleService


def _setup():
    now = datetime.now(timezone.utc)
    admin = Account("admin", "admin@example.com", hash_password("admin-password-123"), role=AccountRole.ADMIN)
    user = Account("user", "user@example.com", hash_password("user-password-123"))
    accounts = InMemoryAccountRepository([admin, user])
    sessions = InMemorySessionRepository()
    auth = AuthenticationService(accounts, sessions)
    _, user_token = auth.login(user.email, "user-password-123")
    licenses = InMemoryLicenseRepository([License("lic-1", user.account_id, now - timedelta(minutes=1), now + timedelta(days=30), entitlements=Entitlements(max_devices=1), status=LicenseStatus.ACTIVE)])
    events = InMemoryLicenseEventRepository()
    devices = InMemoryDeviceRepository()
    lifecycle = LicenseLifecycleService(licenses, events)
    api = FastAPI()
    register_admin_routes(api, auth_service=auth, licenses=licenses, events=events, lifecycle=lifecycle, devices=devices)
    return TestClient(api), user_token, devices, events, now


def test_authenticated_user_can_bind_device_without_secret_echo():
    client, token, devices, events, _ = _setup()
    response = client.post("/devices/bind", headers={"Authorization": f"Bearer {token}"}, json={"license_id": "lic-1", "device_secret": "a" * 64})
    assert response.status_code == 200
    body = response.json()
    assert body["bound"] is True
    assert body["code"] == "DEVICE_REGISTERED"
    assert body["device"]["license_id"] == "lic-1"
    assert "device_key_hash" not in body
    assert "device_secret" not in str(body)
    assert len(devices.list_for_license("lic-1")) == 1
    assert events.list_for_license("lic-1")[0].action == "DEVICE_REGISTERED"


def test_second_device_is_rejected_by_server_limit():
    client, token, _, _, _ = _setup()
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post("/devices/bind", headers=headers, json={"license_id": "lic-1", "device_secret": "a" * 64}).status_code == 200
    response = client.post("/devices/bind", headers=headers, json={"license_id": "lic-1", "device_secret": "b" * 64})
    assert response.status_code == 409
    assert response.json()["detail"] == "DEVICE_LIMIT_REACHED"


def test_same_device_reuses_binding_and_revoked_device_cannot_rebind():
    client, token, devices, _, now = _setup()
    headers = {"Authorization": f"Bearer {token}"}
    first = client.post("/devices/bind", headers=headers, json={"license_id": "lic-1", "device_secret": "a" * 64}).json()
    second = client.post("/devices/bind", headers=headers, json={"license_id": "lic-1", "device_secret": "a" * 64})
    assert second.status_code == 200
    assert second.json()["code"] == "DEVICE_REUSED"
    assert second.json()["device"]["device_id"] == first["device"]["device_id"]
    assert devices.revoke(first["device"]["device_id"], now + timedelta(minutes=1)) is not None
    rebound = client.post("/devices/bind", headers=headers, json={"license_id": "lic-1", "device_secret": "a" * 64})
    assert rebound.status_code == 403
    assert rebound.json()["detail"] == "DEVICE_REVOKED"


def test_binding_requires_auth_and_does_not_cross_account_license_boundary():
    client, token, _, _, _ = _setup()
    assert client.post("/devices/bind", json={"license_id": "lic-1", "device_secret": "a" * 64}).status_code == 401
    response = client.post("/devices/bind", headers={"Authorization": f"Bearer {token}"}, json={"license_id": "missing", "device_secret": "a" * 64})
    assert response.status_code == 403
    assert response.json()["detail"] == "LICENSE_NOT_FOUND"


def test_binding_rejects_short_secret():
    client, token, _, _, _ = _setup()
    response = client.post("/devices/bind", headers={"Authorization": f"Bearer {token}"}, json={"license_id": "lic-1", "device_secret": "too-short"})
    assert response.status_code == 422
