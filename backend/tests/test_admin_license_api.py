from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, AccountRole, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.admin_api import register_admin_routes
from otimizer_api.auth import AuthenticationService
from otimizer_api.devices import Device, InMemoryDeviceRepository
from otimizer_api.licensing import InMemoryLicenseEventRepository, InMemoryLicenseRepository, License, LicenseLifecycleService


def _setup():
    now = datetime.now(timezone.utc)
    admin = Account("admin", "admin@example.com", hash_password("admin-password-123"), role=AccountRole.ADMIN)
    user = Account("user", "user@example.com", hash_password("user-password-123"))
    accounts = InMemoryAccountRepository([admin, user])
    sessions = InMemorySessionRepository()
    auth = AuthenticationService(accounts, sessions)
    _, admin_token = auth.login(admin.email, "admin-password-123")
    _, user_token = auth.login(user.email, "user-password-123")
    licenses = InMemoryLicenseRepository()
    events = InMemoryLicenseEventRepository()
    devices = InMemoryDeviceRepository()
    lifecycle = LicenseLifecycleService(licenses, events)
    api = FastAPI()
    register_admin_routes(api, auth_service=auth, licenses=licenses, events=events, lifecycle=lifecycle, devices=devices)
    return TestClient(api), admin_token, user_token, user, licenses, events, devices, now


def test_admin_endpoints_require_authentication_and_admin_role():
    client, admin_token, user_token, *_ = _setup()
    assert client.get("/admin/licenses").status_code == 401
    assert client.get("/admin/licenses", headers={"Authorization": f"Bearer {user_token}"}).status_code == 403
    assert client.get("/admin/licenses", headers={"Authorization": f"Bearer {admin_token}"}).status_code == 200


def test_admin_can_generate_query_and_read_history_without_secret_leak():
    client, admin_token, _, user, licenses, events, *_ = _setup()
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/admin/licenses", headers=headers, json={"account_id": user.account_id, "plan": "pro", "duration_days": 30, "max_devices": 2})
    assert response.status_code == 200
    body = response.json()
    license_id = body["license_id"]
    assert body["status"] == "GERADA"
    assert body["license_key"]
    assert "device_key_hash" not in body
    assert client.get(f"/admin/licenses/{license_id}", headers=headers).status_code == 200
    history = client.get(f"/admin/licenses/{license_id}/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["count"] == 1
    assert history.json()["items"][0]["action"] == "GENERATED"


def test_admin_lifecycle_is_server_authoritative_and_audited():
    client, admin_token, _, user, *_ = _setup()
    headers = {"Authorization": f"Bearer {admin_token}"}
    generated = client.post("/admin/licenses", headers=headers, json={"account_id": user.account_id, "duration_days": 30}).json()
    license_id = generated["license_id"]
    assert client.post(f"/admin/licenses/{license_id}/activate", headers=headers).json()["status"] == "ATIVA"
    assert client.post(f"/admin/licenses/{license_id}/suspend", headers=headers, json={"reason": "billing review"}).status_code == 200
    assert client.post(f"/admin/licenses/{license_id}/reactivate", headers=headers).status_code == 200
    assert client.post(f"/admin/licenses/{license_id}/renew", headers=headers, json={"duration_days": 30}).status_code == 200
    revoked = client.post(f"/admin/licenses/{license_id}/revoke", headers=headers, json={"reason": "administrative closure"})
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "REVOGADA"
    assert client.post(f"/admin/licenses/{license_id}/activate", headers=headers).status_code == 409
    history = client.get(f"/admin/licenses/{license_id}/history", headers=headers).json()["items"]
    assert [item["action"] for item in history] == ["GENERATED", "ACTIVATED", "SUSPENDED", "REACTIVATED", "RENEWED", "REVOKED"]


def test_admin_device_listing_and_revocation_never_exposes_secret_hash():
    client, admin_token, _, user, licenses, events, devices, now = _setup()
    headers = {"Authorization": f"Bearer {admin_token}"}
    record = License("lic-1", user.account_id, now, now + timedelta(days=30), license_key="safe-key")
    licenses.save(record)
    device = Device("dev-1", user.account_id, record.license_id, "secret-hash", now, now)
    devices.register(device, 1)
    listed = client.get(f"/admin/licenses/{record.license_id}/devices", headers=headers)
    assert listed.status_code == 200
    item = listed.json()["items"][0]
    assert item["device_id"] == "dev-1"
    assert "device_key_hash" not in item
    revoked = client.post("/admin/devices/dev-1/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["active"] is False
