"""Durable SQLite repositories for Otimizer account, session, license and payment state."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .accounts import Account, AccountRepository, AccountRole, Session, SessionRepository
from .auth import AuthenticationService
from .licensing import Entitlements, License, LicenseAuthorizer, LicenseEvent, LicenseEventRepository, LicenseRepository, LicenseStatus
from .payments import PaymentRepository, PaymentStatus, PixCharge


class SQLiteDatabase:
    """Owns the database connection policy and performs additive migrations."""

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    role TEXT NOT NULL DEFAULT 'USER'
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at TEXT NOT NULL,
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_token_hash ON sessions(token_hash);

                CREATE TABLE IF NOT EXISTS licenses (
                    license_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    starts_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    route_optimization INTEGER NOT NULL DEFAULT 1,
                    max_devices INTEGER NOT NULL DEFAULT 1,
                    max_routes_per_day INTEGER,
                    price_cents INTEGER NOT NULL DEFAULT 0,
                    revoked_at TEXT,
                    license_key TEXT,
                    status TEXT NOT NULL DEFAULT 'ATIVA',
                    activated_at TEXT,
                    last_renewal_at TEXT,
                    renewal_count INTEGER NOT NULL DEFAULT 0,
                    last_access_at TEXT,
                    plan TEXT NOT NULL DEFAULT 'default'
                );
                CREATE INDEX IF NOT EXISTS idx_licenses_account_dates
                    ON licenses(account_id, starts_at, expires_at);

                CREATE TABLE IF NOT EXISTS license_events (
                    event_id TEXT PRIMARY KEY,
                    license_id TEXT NOT NULL REFERENCES licenses(license_id),
                    action TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    actor_account_id TEXT REFERENCES accounts(account_id),
                    previous_status TEXT,
                    new_status TEXT,
                    reason TEXT,
                    metadata_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_license_events_license_time
                    ON license_events(license_id, occurred_at);

                CREATE TABLE IF NOT EXISTS payments (
                    payment_id TEXT PRIMARY KEY,
                    account_id TEXT NOT NULL REFERENCES accounts(account_id),
                    license_id TEXT NOT NULL REFERENCES licenses(license_id),
                    amount_cents INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    pix_copy_paste TEXT NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_payments_account ON payments(account_id);
                CREATE INDEX IF NOT EXISTS idx_payments_license ON payments(license_id);
                """
            )
            self._migrate_legacy_schema(connection)

    @staticmethod
    def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
        account_columns = {row["name"] for row in connection.execute("PRAGMA table_info(accounts)")}
        if "role" not in account_columns:
            connection.execute("ALTER TABLE accounts ADD COLUMN role TEXT NOT NULL DEFAULT 'USER'")

        license_columns = {row["name"] for row in connection.execute("PRAGMA table_info(licenses)")}
        additions = {
            "price_cents": "INTEGER NOT NULL DEFAULT 0",
            "license_key": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'ATIVA'",
            "activated_at": "TEXT",
            "last_renewal_at": "TEXT",
            "renewal_count": "INTEGER NOT NULL DEFAULT 0",
            "last_access_at": "TEXT",
            "plan": "TEXT NOT NULL DEFAULT 'default'",
        }
        for name, definition in additions.items():
            if name not in license_columns:
                connection.execute(f"ALTER TABLE licenses ADD COLUMN {name} {definition}")

        # Legacy rows remain valid. Keys are backfilled before the uniqueness index.
        rows = connection.execute("SELECT license_id, license_key FROM licenses").fetchall()
        for row in rows:
            if not row["license_key"]:
                connection.execute(
                    "UPDATE licenses SET license_key = ? WHERE license_id = ?",
                    (License(license_id=row["license_id"], account_id="migration", starts_at=datetime.now(timezone.utc), expires_at=datetime.now(timezone.utc) + timedelta(days=1)).license_key, row["license_id"]),
                )
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_licenses_license_key ON licenses(license_key)")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS license_events (
                event_id TEXT PRIMARY KEY,
                license_id TEXT NOT NULL REFERENCES licenses(license_id),
                action TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                actor_account_id TEXT REFERENCES accounts(account_id),
                previous_status TEXT,
                new_status TEXT,
                reason TEXT,
                metadata_json TEXT
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_license_events_license_time ON license_events(license_id, occurred_at)")


class SQLiteAccountRepository(AccountRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, account: Account) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO accounts(account_id, email, password_hash, active, role)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    email=excluded.email, password_hash=excluded.password_hash,
                    active=excluded.active, role=excluded.role
                """,
                (account.account_id, account.email.strip().casefold(), account.password_hash, int(account.active), account.role.value),
            )

    def get_by_email(self, email: str) -> Account | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT account_id, email, password_hash, active, role FROM accounts WHERE email = ?", (email.strip().casefold(),)).fetchone()
        return _account_from_row(row)

    def get_by_id(self, account_id: str) -> Account | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT account_id, email, password_hash, active, role FROM accounts WHERE account_id = ?", (account_id,)).fetchone()
        return _account_from_row(row)


class SQLiteSessionRepository(SessionRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, session: Session) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(session_id, account_id, token_hash, expires_at, revoked_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    account_id=excluded.account_id, token_hash=excluded.token_hash,
                    expires_at=excluded.expires_at, revoked_at=excluded.revoked_at
                """,
                (session.session_id, session.account_id, session.token_hash, _iso(session.expires_at), _iso(session.revoked_at) if session.revoked_at else None),
            )

    def get_by_token_hash(self, token_hash: str) -> Session | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT session_id, account_id, token_hash, expires_at, revoked_at FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
        return _session_from_row(row)

    def revoke(self, session_id: str, revoked_at: datetime) -> None:
        with self.database.connect() as connection:
            connection.execute("UPDATE sessions SET revoked_at = ? WHERE session_id = ?", (_iso(revoked_at), session_id))


class SQLiteLicenseRepository(LicenseRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, license_record: License) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO licenses(
                    license_id, account_id, starts_at, expires_at, route_optimization,
                    max_devices, max_routes_per_day, price_cents, revoked_at, license_key,
                    status, activated_at, last_renewal_at, renewal_count, last_access_at, plan
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(license_id) DO UPDATE SET
                    account_id=excluded.account_id, starts_at=excluded.starts_at, expires_at=excluded.expires_at,
                    route_optimization=excluded.route_optimization, max_devices=excluded.max_devices,
                    max_routes_per_day=excluded.max_routes_per_day, price_cents=excluded.price_cents,
                    revoked_at=excluded.revoked_at, license_key=excluded.license_key, status=excluded.status,
                    activated_at=excluded.activated_at, last_renewal_at=excluded.last_renewal_at,
                    renewal_count=excluded.renewal_count, last_access_at=excluded.last_access_at, plan=excluded.plan
                """,
                (license_record.license_id, license_record.account_id, _iso(license_record.starts_at), _iso(license_record.expires_at), int(license_record.entitlements.route_optimization), license_record.entitlements.max_devices, license_record.entitlements.max_routes_per_day, license_record.price_cents, _iso(license_record.revoked_at) if license_record.revoked_at else None, license_record.license_key, license_record.status.value, _iso(license_record.activated_at) if license_record.activated_at else None, _iso(license_record.last_renewal_at) if license_record.last_renewal_at else None, license_record.renewal_count, _iso(license_record.last_access_at) if license_record.last_access_at else None, license_record.plan),
            )

    def get_by_id(self, license_id: str) -> License | None:
        with self.database.connect() as connection:
            row = connection.execute(_LICENSE_SELECT + " WHERE license_id = ?", (license_id,)).fetchone()
        return _license_from_row(row)

    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        current = _iso(_utc(now))
        with self.database.connect() as connection:
            row = connection.execute(_LICENSE_SELECT + " WHERE account_id = ? AND starts_at <= ? AND expires_at > ? AND revoked_at IS NULL AND status = ? ORDER BY expires_at DESC LIMIT 1", (account_id, current, current, LicenseStatus.ACTIVE.value)).fetchone()
        return _license_from_row(row)


class SQLiteLicenseEventRepository(LicenseEventRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def append(self, event: LicenseEvent) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "INSERT INTO license_events(event_id, license_id, action, occurred_at, actor_account_id, previous_status, new_status, reason, metadata_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event.event_id, event.license_id, event.action, _iso(event.occurred_at), event.actor_account_id, event.previous_status.value if event.previous_status else None, event.new_status.value if event.new_status else None, event.reason, event.metadata_json),
            )

    def list_for_license(self, license_id: str) -> list[LicenseEvent]:
        with self.database.connect() as connection:
            rows = connection.execute("SELECT event_id, license_id, action, occurred_at, actor_account_id, previous_status, new_status, reason, metadata_json FROM license_events WHERE license_id = ? ORDER BY occurred_at ASC, event_id ASC", (license_id,)).fetchall()
        return [_license_event_from_row(row) for row in rows]


class SQLitePaymentRepository(PaymentRepository):
    """Durable payment store with atomic payment/license settlement."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, charge: PixCharge) -> None:
        if not charge.license_id:
            raise ValueError("payment must be bound to a license")
        if charge.amount_cents <= 0:
            raise ValueError("payment amount must be positive")
        with self.database.connect() as connection:
            connection.execute("INSERT INTO payments(payment_id, account_id, license_id, amount_cents, expires_at, pix_copy_paste, status) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(payment_id) DO UPDATE SET account_id=excluded.account_id, license_id=excluded.license_id, amount_cents=excluded.amount_cents, expires_at=excluded.expires_at, pix_copy_paste=excluded.pix_copy_paste, status=excluded.status", (charge.payment_id, charge.account_id, charge.license_id, charge.amount_cents, _iso(charge.expires_at), charge.pix_copy_paste, charge.status.value))

    def get(self, payment_id: str) -> PixCharge | None:
        with self.database.connect() as connection:
            row = connection.execute("SELECT payment_id, account_id, license_id, amount_cents, expires_at, pix_copy_paste, status FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
        return _payment_from_row(row)

    def settle_confirmed_payment(self, payment_id: str, now: datetime) -> License:
        current = _utc(now)
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            payment_row = connection.execute("SELECT payment_id, account_id, license_id, amount_cents, expires_at, pix_copy_paste, status FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
            if payment_row is None:
                raise KeyError(payment_id)
            charge = _payment_from_row(payment_row)
            assert charge is not None
            license_row = connection.execute(_LICENSE_SELECT + " WHERE license_id = ?", (charge.license_id,)).fetchone()
            license_record = _license_from_row(license_row)
            if license_record is None or license_record.account_id != charge.account_id:
                raise ValueError("payment is not bound to a valid account license")
            if charge.status == PaymentStatus.SETTLED:
                return license_record
            if charge.status != PaymentStatus.CONFIRMED:
                raise ValueError(f"payment is not confirmed: {charge.status.value}")
            if license_record.revoked_at is not None or license_record.status == LicenseStatus.REVOKED:
                raise ValueError("cannot activate a revoked license")
            duration = license_record.expires_at - license_record.starts_at
            if duration <= timedelta(0):
                raise ValueError("license duration must be positive")
            start = max(license_record.expires_at, current)
            activated = replace(license_record, expires_at=start + duration, status=LicenseStatus.ACTIVE, last_renewal_at=current, renewal_count=license_record.renewal_count + 1)
            connection.execute("UPDATE licenses SET expires_at=?, status=?, last_renewal_at=?, renewal_count=? WHERE license_id=?", (_iso(activated.expires_at), activated.status.value, _iso(activated.last_renewal_at), activated.renewal_count, activated.license_id))
            updated = connection.execute("UPDATE payments SET status=? WHERE payment_id=? AND status=?", (PaymentStatus.SETTLED.value, payment_id, PaymentStatus.CONFIRMED.value))
            if updated.rowcount != 1:
                raise RuntimeError("payment settlement lost its confirmation state")
            return activated


_LICENSE_SELECT = """
SELECT license_id, account_id, starts_at, expires_at, route_optimization,
       max_devices, max_routes_per_day, price_cents, revoked_at, license_key,
       status, activated_at, last_renewal_at, renewal_count, last_access_at, plan
FROM licenses
"""


def build_sqlite_services(path: str | Path) -> tuple[SQLiteDatabase, AuthenticationService, LicenseAuthorizer]:
    database = SQLiteDatabase(path)
    accounts = SQLiteAccountRepository(database)
    sessions = SQLiteSessionRepository(database)
    licenses = SQLiteLicenseRepository(database)
    return database, AuthenticationService(accounts, sessions), LicenseAuthorizer(licenses)


def _account_from_row(row: sqlite3.Row | None) -> Account | None:
    if row is None:
        return None
    return Account(account_id=row["account_id"], email=row["email"], password_hash=row["password_hash"], active=bool(row["active"]), role=AccountRole(row["role"]))


def _session_from_row(row: sqlite3.Row | None) -> Session | None:
    if row is None:
        return None
    return Session(session_id=row["session_id"], account_id=row["account_id"], token_hash=row["token_hash"], expires_at=_parse_datetime(row["expires_at"]), revoked_at=_parse_datetime(row["revoked_at"]) if row["revoked_at"] else None)


def _license_from_row(row: sqlite3.Row | None) -> License | None:
    if row is None:
        return None
    return License(license_id=row["license_id"], account_id=row["account_id"], starts_at=_parse_datetime(row["starts_at"]), expires_at=_parse_datetime(row["expires_at"]), entitlements=Entitlements(route_optimization=bool(row["route_optimization"]), max_devices=int(row["max_devices"]), max_routes_per_day=row["max_routes_per_day"]), revoked_at=_parse_datetime(row["revoked_at"]) if row["revoked_at"] else None, price_cents=int(row["price_cents"]), license_key=row["license_key"], status=LicenseStatus(row["status"]), activated_at=_parse_datetime(row["activated_at"]) if row["activated_at"] else None, last_renewal_at=_parse_datetime(row["last_renewal_at"]) if row["last_renewal_at"] else None, renewal_count=int(row["renewal_count"]), last_access_at=_parse_datetime(row["last_access_at"]) if row["last_access_at"] else None, plan=row["plan"])


def _license_event_from_row(row: sqlite3.Row) -> LicenseEvent:
    return LicenseEvent(event_id=row["event_id"], license_id=row["license_id"], action=row["action"], occurred_at=_parse_datetime(row["occurred_at"]), actor_account_id=row["actor_account_id"], previous_status=LicenseStatus(row["previous_status"]) if row["previous_status"] else None, new_status=LicenseStatus(row["new_status"]) if row["new_status"] else None, reason=row["reason"], metadata_json=row["metadata_json"])


def _payment_from_row(row: sqlite3.Row | None) -> PixCharge | None:
    if row is None:
        return None
    return PixCharge(payment_id=row["payment_id"], account_id=row["account_id"], license_id=row["license_id"], amount_cents=int(row["amount_cents"]), expires_at=_parse_datetime(row["expires_at"]), pix_copy_paste=row["pix_copy_paste"], status=PaymentStatus(row["status"]))


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse_datetime(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
