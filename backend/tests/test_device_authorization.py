from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.auth import AuthenticationService
from otimizer_api.devices import DeviceBindingService, InMemoryDeviceRepository
from otimizer_api.licensing import Entitlements, InMemoryLicenseEventRepository, InMemoryLicenseRepository, License, LicenseAuthorizer
from otimizer_api.main import create_app


class FakeRoutingProvider:
    def table(self, locations):
        from otimizer_importer.routing import TravelMetric
        size = len(locations)
        return tuple(tuple(TravelMetric(abs(row - col) * 1000, abs(row - col) * 60) for col in range(size)) for row in range(size))


def _setup():
    now = datetime.now(timezone.utc)
    account = Account("acct-1", "user@example.com", hash_password("a-strong-development-password"))
    accounts = InMemoryAccountRepository([account])
    auth = AuthenticationService(accounts, InMemorySessionRepository())
    license_record = License("lic-1", "acct-1", now - timedelta(days=1), now + timedelta(days=30), entitlements=Entitlements(max_devices=1))
    licenses = InMemoryLicenseRepository([license_record])
    devices = InMemoryDeviceRepository()
    events = InMemoryLicenseEventRepository()
    binding = DeviceBindingService(licenses, devices, events)
    _, token = auth.login(account.email, "a-strong-development-password")
    client = TestClient(create_app(FakeRoutingProvider(), LicenseAuthorizer(licenses), auth, device_repository=devices))
    return client, token, binding, devices, now


def test_route_requires_device_binding_when_device_repository_is_enabled():
    client, token, *_ = _setup()
    response = client.post(
        "/optimize",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("bad.txt", b"not processed", "text/plain")},
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "DEVICE_BINDING_REQUIRED"


def test_bound_device_is_authorized_and_revoked_device_is_denied():
    client, token, binding, devices, now = _setup()
    allowed, device, code = binding.register("acct-1", "lic-1", "device-secret-abcdefghijklmnopqrstuvwxyz", now)
    assert allowed and code == "DEVICE_REGISTERED"
    headers = {"Authorization": f"Bearer {token}", "X-Otimizer-Device-ID": device.device_id}
    response = client.post("/optimize", headers=headers, files={"file": ("bad.txt", b"not processed", "text/plain")})
    assert response.status_code == 422
    assert response.json()["detail"] == "The uploaded file must be an .xlsx workbook"
    devices.revoke(device.device_id, now + timedelta(minutes=1))
    denied = client.post("/optimize", headers=headers, files={"file": ("bad.txt", b"not processed", "text/plain")})
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "DEVICE_NOT_AUTHORIZED"
