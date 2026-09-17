from datetime import datetime, timedelta, timezone

from otimizer_api.devices import Device, DeviceBindingService, InMemoryDeviceRepository, SQLiteDeviceRepository, hash_device_secret
from otimizer_api.licensing import InMemoryLicenseEventRepository, InMemoryLicenseRepository, License, LicenseStatus, Entitlements
from otimizer_api.persistence import SQLiteAccountRepository, SQLiteDatabase
from otimizer_api.accounts import Account

NOW = datetime(2026, 9, 17, 12, tzinfo=timezone.utc)


def make_license(**kwargs):
    values = dict(license_id="lic-1", account_id="acct-1", starts_at=NOW - timedelta(days=1), expires_at=NOW + timedelta(days=30))
    values.update(kwargs)
    return License(**values)


def test_device_secret_is_stored_as_hash():
    assert hash_device_secret("installation-secret") != "installation-secret"
    assert hash_device_secret("installation-secret") == hash_device_secret("installation-secret")


def test_first_device_registers_and_second_is_rejected_at_limit():
    licenses = InMemoryLicenseRepository([make_license(entitlements=Entitlements(max_devices=1))])
    devices = InMemoryDeviceRepository()
    events = InMemoryLicenseEventRepository()
    service = DeviceBindingService(licenses, devices, events)
    first = service.register("acct-1", "lic-1", "device-a", NOW)
    second = service.register("acct-1", "lic-1", "device-b", NOW)
    assert first[0] is True and first[2] == "DEVICE_REGISTERED"
    assert second[0] is False and second[2] == "DEVICE_LIMIT_REACHED"
    assert len(devices.list_for_license("lic-1")) == 1


def test_same_device_reuses_binding_without_consuming_another_slot():
    licenses = InMemoryLicenseRepository([make_license(entitlements=Entitlements(max_devices=1))])
    devices = InMemoryDeviceRepository()
    service = DeviceBindingService(licenses, devices)
    first = service.register("acct-1", "lic-1", "device-a", NOW)
    second = service.register("acct-1", "lic-1", "device-a", NOW + timedelta(minutes=5))
    assert second[0] is True and second[2] == "DEVICE_REUSED"
    assert second[1].device_id == first[1].device_id
    assert len(devices.list_for_license("lic-1")) == 1


def test_suspended_expired_and_revoked_licenses_cannot_bind():
    for status, expected in ((LicenseStatus.SUSPENDED, "LICENSE_SUSPENDED"), (LicenseStatus.REVOKED, "LICENSE_REVOKED")):
        revoked_at = NOW if status is LicenseStatus.REVOKED else None
        license_record = make_license(status=status, revoked_at=revoked_at)
        service = DeviceBindingService(InMemoryLicenseRepository([license_record]), InMemoryDeviceRepository())
        allowed, device, code = service.register("acct-1", "lic-1", "device-a", NOW)
        assert not allowed and device is None and code == expected

    expired = make_license(expires_at=NOW)
    service = DeviceBindingService(InMemoryLicenseRepository([expired]), InMemoryDeviceRepository())
    assert service.register("acct-1", "lic-1", "device-a", NOW)[2] == "LICENSE_EXPIRED"


def test_revoking_device_frees_license_capacity():
    license_record = make_license(entitlements=Entitlements(max_devices=1))
    devices = InMemoryDeviceRepository()
    service = DeviceBindingService(InMemoryLicenseRepository([license_record]), devices)
    first = service.register("acct-1", "lic-1", "device-a", NOW)
    assert service.register("acct-1", "lic-1", "device-b", NOW)[2] == "DEVICE_LIMIT_REACHED"
    assert service.revoke("acct-1", first[1].device_id, NOW + timedelta(minutes=1))
    assert service.register("acct-1", "lic-1", "device-b", NOW + timedelta(minutes=2))[2] == "DEVICE_REGISTERED"


def test_sqlite_device_binding_survives_new_repository_instance(tmp_path):
    database = SQLiteDatabase(tmp_path / "devices.db")
    SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
    license_record = make_license()
    from otimizer_api.persistence import SQLiteLicenseRepository
    SQLiteLicenseRepository(database).save(license_record)
    first_repo = SQLiteDeviceRepository(database)
    service = DeviceBindingService(SQLiteLicenseRepository(database), first_repo)
    allowed, device, code = service.register("acct-1", "lic-1", "device-a", NOW)
    assert allowed and code == "DEVICE_REGISTERED"
    second_repo = SQLiteDeviceRepository(database)
    restored = second_repo.list_for_license("lic-1")
    assert len(restored) == 1
    assert restored[0].device_id == device.device_id
    assert restored[0].device_key_hash == hash_device_secret("device-a")


def test_sqlite_device_limit_is_enforced_durably():
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        database = SQLiteDatabase(f"{directory}/devices.db")
        SQLiteAccountRepository(database).save(Account("acct-1", "user@example.com", "hash"))
        from otimizer_api.persistence import SQLiteLicenseRepository
        SQLiteLicenseRepository(database).save(make_license(entitlements=Entitlements(max_devices=1)))
        repository = SQLiteDeviceRepository(database)
        service = DeviceBindingService(SQLiteLicenseRepository(database), repository)
        assert service.register("acct-1", "lic-1", "device-a", NOW)[2] == "DEVICE_REGISTERED"
        assert service.register("acct-1", "lic-1", "device-b", NOW)[2] == "DEVICE_LIMIT_REACHED"
