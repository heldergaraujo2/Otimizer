"""Durable SQLite repositories for Otimizer account, session, license and payment state."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .accounts import Account, AccountRepository, Session, SessionRepository
from .auth import AuthenticationService
from .licensing import Entitlements, License, LicenseAuthorizer, LicenseRepository
from .payments import PaymentRepository, PaymentStatus, PixCharge


class SQLiteDatabase:
    """Owns the database connection policy and schema initialization."""

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
                    active INTEGER NOT NULL DEFAULT 1
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
                    revoked_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_licenses_account_dates
                    ON licenses(account_id, starts_at, expires_at);

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
            columns = {row["name"] for row in connection.execute("PRAGMA table_info(licenses)")}
            if "price_cents" not in columns:
                connection.execute("ALTER TABLE licenses ADD COLUMN price_cents INTEGER NOT NULL DEFAULT 0")


class SQLiteAccountRepository(AccountRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, account: Account) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO accounts(account_id, email, password_hash, active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(account_id) DO UPDATE SET
                    email=excluded.email, password_hash=excluded.password_hash, active=excluded.active
                """,
                (account.account_id, account.email.strip().casefold(), account.password_hash, int(account.active)),
            )

    def get_by_email(self, email: str) -> Account | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT account_id, email, password_hash, active FROM accounts WHERE email = ?",
                (email.strip().casefold(),),
            ).fetchone()
        return _account_from_row(row)

    def get_by_id(self, account_id: str) -> Account | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT account_id, email, password_hash, active FROM accounts WHERE account_id = ?",
                (account_id,),
            ).fetchone()
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
                (
                    session.session_id,
                    session.account_id,
                    session.token_hash,
                    _iso(session.expires_at),
                    _iso(session.revoked_at) if session.revoked_at else None,
                ),
            )

    def get_by_token_hash(self, token_hash: str) -> Session | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT session_id, account_id, token_hash, expires_at, revoked_at "
                "FROM sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
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
                    license_id, account_id, starts_at, expires_at,
                    route_optimization, max_devices, max_routes_per_day, price_cents, revoked_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(license_id) DO UPDATE SET
                    account_id=excluded.account_id, starts_at=excluded.starts_at,
                    expires_at=excluded.expires_at, route_optimization=excluded.route_optimization,
                    max_devices=excluded.max_devices, max_routes_per_day=excluded.max_routes_per_day,
                    price_cents=excluded.price_cents, revoked_at=excluded.revoked_at
                """,
                (
                    license_record.license_id,
                    license_record.account_id,
                    _iso(license_record.starts_at),
                    _iso(license_record.expires_at),
                    int(license_record.entitlements.route_optimization),
                    license_record.entitlements.max_devices,
                    license_record.entitlements.max_routes_per_day,
                    license_record.price_cents,
                    _iso(license_record.revoked_at) if license_record.revoked_at else None,
                ),
            )

    def get_active_license(self, account_id: str, now: datetime) -> License | None:
        current = _iso(_utc(now))
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT license_id, account_id, starts_at, expires_at,
                       route_optimization, max_devices, max_routes_per_day, price_cents, revoked_at
                FROM licenses
                WHERE account_id = ? AND starts_at <= ? AND expires_at > ? AND revoked_at IS NULL
                ORDER BY expires_at DESC LIMIT 1
                """,
                (account_id, current, current),
            ).fetchone()
        return _license_from_row(row)


class SQLitePaymentRepository(PaymentRepository):
    """Durable payment store; amount and status are persisted independently."""

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def save(self, charge: PixCharge) -> None:
        if not charge.license_id:
            raise ValueError("payment must be bound to a license")
        if charge.amount_cents <= 0:
            raise ValueError("payment amount must be positive")
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO payments(
                    payment_id, account_id, license_id, amount_cents,
                    expires_at, pix_copy_paste, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(payment_id) DO UPDATE SET
                    account_id=excluded.account_id, license_id=excluded.license_id,
                    amount_cents=excluded.amount_cents, expires_at=excluded.expires_at,
                    pix_copy_paste=excluded.pix_copy_paste, status=excluded.status
                """,
                (
                    charge.payment_id,
                    charge.account_id,
                    charge.license_id,
                    charge.amount_cents,
                    _iso(charge.expires_at),
                    charge.pix_copy_paste,
                    charge.status.value,
                ),
            )

    def get(self, payment_id: str) -> PixCharge | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT payment_id, account_id, license_id, amount_cents,
                       expires_at, pix_copy_paste, status
                FROM payments WHERE payment_id = ?
                """,
                (payment_id,),
            ).fetchone()
        return _payment_from_row(row)


def build_sqlite_services(path: str | Path) -> tuple[SQLiteDatabase, AuthenticationService, LicenseAuthorizer]:
    """Build the durable authentication/licensing stack for one backend instance."""
    database = SQLiteDatabase(path)
    accounts = SQLiteAccountRepository(database)
    sessions = SQLiteSessionRepository(database)
    licenses = SQLiteLicenseRepository(database)
    return database, AuthenticationService(accounts, sessions), LicenseAuthorizer(licenses)


def _account_from_row(row: sqlite3.Row | None) -> Account | None:
    if row is None:
        return None
    return Account(account_id=row["account_id"], email=row["email"], password_hash=row["password_hash"], active=bool(row["active"]))


def _session_from_row(row: sqlite3.Row | None) -> Session | None:
    if row is None:
        return None
    return Session(
        session_id=row["session_id"], account_id=row["account_id"], token_hash=row["token_hash"],
        expires_at=_parse_datetime(row["expires_at"]),
        revoked_at=_parse_datetime(row["revoked_at"]) if row["revoked_at"] else None,
    )


def _license_from_row(row: sqlite3.Row | None) -> License | None:
    if row is None:
        return None
    return License(
        license_id=row["license_id"], account_id=row["account_id"],
        starts_at=_parse_datetime(row["starts_at"]), expires_at=_parse_datetime(row["expires_at"]),
        entitlements=Entitlements(
            route_optimization=bool(row["route_optimization"]),
            max_devices=int(row["max_devices"]), max_routes_per_day=row["max_routes_per_day"],
        ),
        revoked_at=_parse_datetime(row["revoked_at"]) if row["revoked_at"] else None,
        price_cents=int(row["price_cents"]),
    )


def _payment_from_row(row: sqlite3.Row | None) -> PixCharge | None:
    if row is None:
        return None
    return PixCharge(
        payment_id=row["payment_id"], account_id=row["account_id"], license_id=row["license_id"],
        amount_cents=int(row["amount_cents"]), expires_at=_parse_datetime(row["expires_at"]),
        pix_copy_paste=row["pix_copy_paste"], status=PaymentStatus(row["status"]),
    )


def _iso(value: datetime) -> str:
    return _utc(value).isoformat()


def _parse_datetime(value: str) -> datetime:
    return _utc(datetime.fromisoformat(value))


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
