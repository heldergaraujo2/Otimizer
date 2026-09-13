"""Authentication service for account login and bearer sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .accounts import (
    Account,
    AccountRepository,
    SessionRepository,
    authenticate_session,
    create_session,
    verify_password,
)


@dataclass(frozen=True)
class AuthenticatedAccount:
    account: Account
    session_id: str


class AuthenticationService:
    def __init__(self, accounts: AccountRepository, sessions: SessionRepository) -> None:
        self.accounts = accounts
        self.sessions = sessions

    def login(self, email: str, password: str) -> tuple[Account, str] | None:
        account = self.accounts.get_by_email(email)
        if account is None or not account.active or not verify_password(password, account.password_hash):
            return None
        return account, create_session(account.account_id, self.sessions)

    def authenticate_bearer(self, authorization: str | None) -> AuthenticatedAccount | None:
        if not authorization or not authorization.startswith("Bearer "):
            return None
        token = authorization[7:].strip()
        if not token:
            return None
        session = authenticate_session(token, self.sessions)
        if session is None:
            return None
        account = self.accounts.get_by_id(session.account_id)
        if account is None or not account.active:
            return None
        return AuthenticatedAccount(account=account, session_id=session.session_id)

    def logout(self, authorization: str | None) -> bool:
        authenticated = self.authenticate_bearer(authorization)
        if authenticated is None:
            return False
        self.sessions.revoke(authenticated.session_id, datetime.now(timezone.utc))
        return True
