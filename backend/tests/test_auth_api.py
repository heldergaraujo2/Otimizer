from fastapi.testclient import TestClient

from otimizer_api.accounts import Account, InMemoryAccountRepository, InMemorySessionRepository, hash_password
from otimizer_api.auth import AuthenticationService
from otimizer_api.main import create_app


def auth_service():
    accounts = InMemoryAccountRepository([
        Account("acct-1", "user@example.com", hash_password("a-strong-development-password")),
    ])
    return AuthenticationService(accounts, InMemorySessionRepository())


def test_login_returns_bearer_token():
    client = TestClient(create_app(auth_service=auth_service()))
    response = client.post("/auth/login", json={"email": "USER@example.com", "password": "a-strong-development-password"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["account"] == {"account_id": "acct-1", "email": "user@example.com", "role": "USER"}


def test_login_hides_account_existence():
    client = TestClient(create_app(auth_service=auth_service()))
    response = client.post("/auth/login", json={"email": "missing@example.com", "password": "a-strong-development-password"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


def test_me_and_logout_use_bearer_session():
    client = TestClient(create_app(auth_service=auth_service()))
    login = client.post("/auth/login", json={"email": "user@example.com", "password": "a-strong-development-password"})
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["account_id"] == "acct-1"
    assert me.json()["role"] == "USER"
    logout = client.post("/auth/logout", headers=headers)
    assert logout.status_code == 200
    assert logout.json() == {"logged_out": True}
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_me_rejects_invalid_bearer_token():
    client = TestClient(create_app(auth_service=auth_service()))
    response = client.get("/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401
