"""Account and session domain primitives for Otimizer."""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from hashlib import sha256
from secrets import token_urlsafe
from typing import Protocol
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher()

class AccountRole(StrEnum):
    USER = "USER"
    ADMIN = "ADMIN"

@dataclass(frozen=True)
class Account:
    account_id: str
    email: str
    password_hash: str
    active: bool = True
    role: AccountRole = AccountRole.USER

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
    def __init__(self) -> None: self._sessions: dict[str, Session] = {}
    def save(self, session: Session) -> None: self._sessions[session.session_id] = session
    def get_by_token_hash(self, token_hash: str) -> Session | None:
        return next((item for item in self._sessions.values() if item.token_hash == token_hash), None)
    def revoke(self, session_id: str, revoked_at: datetime) -> None:
        current = self._sessions.get(session_id)
        if current is not None:
            self._sessions[session_id] = Session(current.session_id, current.account_id, current.token_hash, current.expires_at, revoked_at)

def hash_password(password: str) -> str:
    if len(password) < 12: raise ValueError("Password must contain at least 12 characters")
    return _PASSWORD_HASHER.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    try: return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError): return False

def create_session(account_id: str, repository: SessionRepository, lifetime: timedelta = timedelta(hours=12)) -> str:
    raw_token = token_urlsafe(32)
    repository.save(Session(token_urlsafe(18), account_id, sha256(raw_token.encode()).hexdigest(), _utc(None) + lifetime))
    return raw_token

def authenticate_session(token: str, repository: SessionRepository, now: datetime | None = None) -> Session | None:
    if not token: return None
    session = repository.get_by_token_hash(sha256(token.encode()).hexdigest())
    return session if session is not None and session.is_active(now) else None

def _utc(value: datetime | None) -> datetime:
    current = value or datetime.now(timezone.utc)
    return current.replace(tzinfo=timezone.utc) if current.tzinfo is None else current.astimezone(timezone.utc)
