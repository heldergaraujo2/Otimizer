"""Server-side device binding and license device-limit enforcement."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol

from .licensing import License, LicenseEvent, LicenseEventRepository, LicenseRepository, LicenseStatus, create_license_event


@dataclass(frozen=True)
class Device:
    device_id: str
    account_id: str
    license_id: str
    device_key_hash: str
    created_at: datetime
    last_seen_at: datetime
    revoked_at: datetime | None = None

    @property
    def active(self) -> bool:
        return self.revoked_at is None


class DeviceRepository(Protocol):
    def register(self, device: Device, max_devices: int) -> tuple[bool, Device | None, str]: ...
    def get(self, device_id: str) -> Device | None: ...
    def list_for_license(self, license_id: str, active_only: bool = True) -> list[Device]: ...
    def revoke(self, device_id: str, revoked_at: datetime) -> Device | None: ...


class InMemoryDeviceRepository:
    def __init__(self, devices: list[Device] | None = None) -> None:
        self._devices = {device.device_id: device for device in devices or []}
    def register(self, device: Device, max_devices: int) -> tuple[bool, Device | None, str]:
        existing = next((item for item in self._devices.values() if item.license_id == device.license_id and item.device_key_hash == device.device_key_hash), None)
        if existing is not None:
            if existing.revoked_at is not None:
                return False, None, "DEVICE_REVOKED"
            refreshed = Device(existing.device_id, existing.account_id, existing.license_id, existing.device_key_hash, existing.created_at, device.last_seen_at, None)
            self._devices[existing.device_id] = refreshed
            return True, refreshed, "DEVICE_REUSED"
        active_count = sum(1 for item in self._devices.values() if item.license_id == device.license_id and item.active)
        if active_count >= max_devices: return False, None, "DEVICE_LIMIT_REACHED"
        self._devices[device.device_id] = device
        return True, device, "DEVICE_REGISTERED"
    def get(self, device_id: str) -> Device | None: return self._devices.get(device_id)
    def list_for_license(self, license_id: str, active_only: bool = True) -> list[Device]: return [item for item in self._devices.values() if item.license_id == license_id and (not active_only or item.active)]
    def revoke(self, device_id: str, revoked_at: datetime) -> Device | None:
        device = self._devices.get(device_id)
        if device is None: return None
        updated = Device(device.device_id, device.account_id, device.license_id, device.device_key_hash, device.created_at, device.last_seen_at, _utc(revoked_at))
        self._devices[device_id] = updated
        return updated


class SQLiteDeviceRepository:
    """Durable repository; capacity changes and audited revocation can be transactional."""
    def __init__(self, database) -> None:
        self.database = database
        with self.database.connect() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS devices (
                device_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES accounts(account_id),
                license_id TEXT NOT NULL REFERENCES licenses(license_id),
                device_key_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                revoked_at TEXT
            )""")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_devices_license_key ON devices(license_id, device_key_hash)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_devices_license_active ON devices(license_id, revoked_at)")
    def register(self, device: Device, max_devices: int) -> tuple[bool, Device | None, str]:
        if max_devices < 1: raise ValueError("max_devices must be at least 1")
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT device_id, account_id, license_id, device_key_hash, created_at, last_seen_at, revoked_at FROM devices WHERE license_id=? AND device_key_hash=?", (device.license_id, device.device_key_hash)).fetchone()
            if row is not None:
                if row["revoked_at"] is not None:
                    return False, None, "DEVICE_REVOKED"
                connection.execute("UPDATE devices SET last_seen_at=? WHERE device_id=?", (_iso(device.last_seen_at), row["device_id"]))
                return True, _device_from_row(row, last_seen_at=device.last_seen_at), "DEVICE_REUSED"
            count = connection.execute("SELECT COUNT(*) FROM devices WHERE license_id=? AND revoked_at IS NULL", (device.license_id,)).fetchone()[0]
            if count >= max_devices: return False, None, "DEVICE_LIMIT_REACHED"
            connection.execute("INSERT INTO devices(device_id, account_id, license_id, device_key_hash, created_at, last_seen_at, revoked_at) VALUES (?, ?, ?, ?, ?, ?, NULL)", (device.device_id, device.account_id, device.license_id, device.device_key_hash, _iso(device.created_at), _iso(device.last_seen_at)))
            return True, device, "DEVICE_REGISTERED"
    def get(self, device_id: str) -> Device | None:
        with self.database.connect() as connection: row = connection.execute("SELECT device_id, account_id, license_id, device_key_hash, created_at, last_seen_at, revoked_at FROM devices WHERE device_id=?", (device_id,)).fetchone()
        return _device_from_row(row)
    def list_for_license(self, license_id: str, active_only: bool = True) -> list[Device]:
        query = "SELECT device_id, account_id, license_id, device_key_hash, created_at, last_seen_at, revoked_at FROM devices WHERE license_id=?"
        params = [license_id]
        if active_only: query += " AND revoked_at IS NULL"
        query += " ORDER BY created_at ASC, device_id ASC"
        with self.database.connect() as connection: rows = connection.execute(query, params).fetchall()
        return [_device_from_row(row) for row in rows]
    def revoke(self, device_id: str, revoked_at: datetime) -> Device | None:
        with self.database.connect() as connection: connection.execute("UPDATE devices SET revoked_at=? WHERE device_id=? AND revoked_at IS NULL", (_iso(revoked_at), device_id))
        return self.get(device_id)
    def revoke_with_event(self, device_id: str, revoked_at: datetime, event: LicenseEvent) -> Device | None:
        current_time = _utc(revoked_at)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT device_id, account_id, license_id, device_key_hash, created_at, last_seen_at, revoked_at FROM devices WHERE device_id=?", (device_id,)).fetchone()
            if row is None or row["revoked_at"] is not None: return None
            connection.execute("UPDATE devices SET revoked_at=? WHERE device_id=? AND revoked_at IS NULL", (_iso(current_time), device_id))
            connection.execute("INSERT INTO license_events(event_id,license_id,action,occurred_at,actor_account_id,previous_status,new_status,reason,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)", (event.event_id,event.license_id,event.action,_iso(event.occurred_at),event.actor_account_id,event.previous_status.value if event.previous_status else None,event.new_status.value if event.new_status else None,event.reason,event.metadata_json))
            return Device(row["device_id"], row["account_id"], row["license_id"], row["device_key_hash"], _parse(row["created_at"]), _parse(row["last_seen_at"]), current_time)


class DeviceBindingService:
    """Binds installations to an active license; the backend is authoritative."""
    def __init__(self, licenses: LicenseRepository, devices: DeviceRepository, events: LicenseEventRepository | None = None) -> None:
        self.licenses = licenses; self.devices = devices; self.events = events
    def register(self, account_id: str, license_id: str, device_secret: str, now: datetime | None = None) -> tuple[bool, Device | None, str]:
        current = _utc(now)
        if not account_id.strip() or not device_secret.strip(): return False, None, "INVALID_DEVICE_CREDENTIAL"
        license_record = self.licenses.get_by_id(license_id)
        if license_record is None or license_record.account_id != account_id: return False, None, "LICENSE_NOT_FOUND"
        if not license_record.is_active(current): return False, None, _license_error(license_record, current)
        device = Device(token_urlsafe(18), account_id, license_id, hash_device_secret(device_secret), current, current)
        allowed, bound, code = self.devices.register(device, license_record.entitlements.max_devices)
        if self.events is not None and code != "DEVICE_LIMIT_REACHED": self.events.append(create_license_event(license_id, code, current, actor_account_id=account_id, new_status=license_record.status, metadata_json='{"device_binding":true}'))
        return allowed, bound, code
    def revoke(self, account_id: str, device_id: str, now: datetime | None = None) -> bool:
        current = _utc(now); device = self.devices.get(device_id)
        if device is None or device.account_id != account_id: return False
        event = create_license_event(device.license_id, "DEVICE_REVOKED", current, actor_account_id=account_id, metadata_json=f'{{"device_id":"{device_id}"}}')
        atomic = getattr(self.devices, "revoke_with_event", None)
        if callable(atomic): return atomic(device_id, current, event) is not None
        revoked = self.devices.revoke(device_id, current)
        if revoked is None: return False
        if self.events is not None: self.events.append(event)
        return True


def hash_device_secret(device_secret: str) -> str:
    if not device_secret.strip(): raise ValueError("device_secret must not be empty")
    return sha256(device_secret.encode("utf-8")).hexdigest()

def _license_error(license_record: License, now: datetime) -> str:
    status = license_record.effective_status(now)
    return {LicenseStatus.EXPIRED: "LICENSE_EXPIRED", LicenseStatus.SUSPENDED: "LICENSE_SUSPENDED", LicenseStatus.REVOKED: "LICENSE_REVOKED"}.get(status, "LICENSE_NOT_ACTIVE")

def _device_from_row(row: sqlite3.Row | None, last_seen_at: datetime | None = None) -> Device | None:
    if row is None: return None
    return Device(row["device_id"], row["account_id"], row["license_id"], row["device_key_hash"], _parse(row["created_at"]), last_seen_at or _parse(row["last_seen_at"]), _parse(row["revoked_at"]) if row["revoked_at"] else None)

def _iso(value: datetime) -> str: return _utc(value).isoformat()
def _parse(value: str) -> datetime: return _utc(datetime.fromisoformat(value))
def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
