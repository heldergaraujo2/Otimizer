from datetime import timedelta

import pytest

from otimizer_api.accounts import (
    Account,
    InMemoryAccountRepository,
    InMemorySessionRepository,
    authenticate_session,
    create_session,
    hash_password,
    verify_password,
)


def test_password_hash_uses_argon2id_and_verifies():
    password = "a-strong-development-password"
    password_hash = hash_password(password)
    assert password_hash != password
    assert password_hash.startswith("$argon2id$")
    assert verify_password(password, password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_password_hash_is_salted():
    password = "a-strong-development-password"
    assert hash_password(password) != hash_password(password)


def test_short_password_is_rejected():
    with pytest.raises(ValueError, match="12 characters"):
        hash_password("too-short")


def test_email_lookup_is_case_insensitive():
    repository = InMemoryAccountRepository([Account("acct-1", "User@Example.com", "hash")])
    assert repository.get_by_email(" user@example.COM ").account_id == "acct-1"


def test_session_stores_only_token_hash_and_can_be_revoked():
    repository = InMemorySessionRepository()
    token = create_session("acct-1", repository, lifetime=timedelta(hours=1))
    session = authenticate_session(token, repository)
    assert session is not None
    assert session.account_id == "acct-1"
    assert token not in session.token_hash

    repository.revoke(session.session_id, session.expires_at - timedelta(minutes=30))
    assert authenticate_session(token, repository) is None
