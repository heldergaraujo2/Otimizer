from datetime import datetime, timedelta, timezone

from otimizer_api.accounts import Account
from otimizer_api.licensing import License
from otimizer_api.persistence import (
    SQLiteAccountRepository,
    SQLiteLicenseRepository,
    build_sqlite_services,
)
from otimizer_api.accounts import hash_password


def test_built_services_share_durable_repositories(tmp_path):
    database, auth, authorizer = build_sqlite_services(tmp_path / "otimizer.db")
    account_repository = SQLiteAccountRepository(database)
    license_repository = SQLiteLicenseRepository(database)
    account_repository.save(Account("acct-1", "user@example.com", hash_password("strong-password-123")))

    now = datetime.now(timezone.utc)
    license_repository.save(
        License("lic-1", "acct-1", now - timedelta(minutes=1), now + timedelta(days=30))
    )

    account, token = auth.login("USER@example.com", "strong-password-123")
    assert account.account_id == "acct-1"
    assert auth.authenticate_bearer(f"Bearer {token}") is not None

    decision = authorizer.authorize_route("acct-1", now)
    assert decision.allowed is True
    assert decision.license is not None
    assert decision.license.license_id == "lic-1"
