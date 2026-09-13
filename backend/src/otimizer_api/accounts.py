"""Account and session domain primitives for Otimizer.

The production adapter will persist accounts and sessions in the database.
This module keeps authentication policy independent from that storage layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol


@dataclass(frozen=True)
class Account:
    account_id: str
    email: str
    password_hash: str
    active: bool = True


@dataclass(frozen=True)
class Session:
    session_id: str
    account_id: str
    token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        current = _utc(now)
        return self.revoked_at is None and current < self.expires_at


class AccountRepository(Protocol):
    def get_by_email(self, email: str) -> Account | None: ...

    def get_by_id(self, account_id: str) -> Account | None: ...


class SessionRepository(Protocol):
    def save(self, session: Session) -> None: ...

    def get_by_token_hash(self, token_hash: str) -> Session | None: ...

    def revoke(self, session_id: str, revoked_at: datetime) -> None: ...


class InMemoryAccountRepository:
    def __init__(self, accounts: list[Account] | None = None) -> None:
        self._accounts = list(accounts or [])

    def get_by_email(self, email: str) -> Account | None:
        target = email.strip().casefold()
        return next((item for item in self._accounts if item.email.casefold() == target), None)

    def get_by_id(self, account_id: str) -> Account | None:
        return next((item for item in self._accounts if item.account_id == account_id), None)


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def save(self, session: Session) -> None:
        self._sessions[session.session_id] = session

    def get_by_token_hash(self, token_hash: str) -> Session | None:
        return next((item for item in self._sessions.values() if item.token_hash == token_hash), None)

    def revoke(self, session_id: str, revoked_at: datetime) -> None:
        current = self._sessions.get(session_id)
        if current is not None:
            self._sessions[session_id] = Session(
                session_id=current.session_id,
                account_id=current.account_id,
                token_hash=current.token_hash,
                expires_at=current.expires_at,
                revoked_at=revoked_at,
            )


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    return sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return sha256(password.encode("utf-8")).hexdigest() == password_hash


def create_session(account_id: str, repository: SessionRepository, lifetime: timedelta = timedelta(hours=12)) -> str:
    raw_token = token_urlsafe(32)
    session = Session(
        session_id=token_urlsafe(18),
        account_id=account_id,
        token_hash=sha256(raw_token.encode("utf-8")).hexdigest(),
        expires_at=_utc(None) + lifetime,
    )
    repository.save(session)
    return raw_token


def authenticate_session(token: str, repository: SessionRepository, now: datetime | None = None) -> Session | None:
    if not token:
        return None
    session = repository.get_by_token_hash(sha256(token.encode("utf-8")).hexdigest())
    if session is None or not session.is_active(now):
        return None
    return session


def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)
