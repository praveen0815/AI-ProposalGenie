"""Registration, login, and access-token protection."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User

PASSWORD = "Correct-horse-1"


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:10]}@example.com"


def _register(api: TestClient, email: str, password: str = PASSWORD, full_name: str = "Ada Lovelace") -> dict:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": full_name},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_register_stores_a_hash_and_returns_a_token(api: TestClient, db_session: Session) -> None:
    email = _email("ada")
    body = _register(api, email)

    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["user"]["email"] == email
    assert "password" not in body["user"]
    stored = db_session.scalar(select(User).where(User.email == email))
    assert stored is not None
    assert stored.password_hash != PASSWORD
    assert stored.password_hash.startswith("$argon2")


def test_duplicate_email_is_rejected_regardless_of_case(api: TestClient) -> None:
    email = _email("ada")
    _register(api, email)

    response = api.post(
        "/api/v1/auth/register",
        json={"email": email.upper(), "password": PASSWORD, "full_name": "Ada Lovelace"},
    )

    assert response.status_code == 409
    assert response.json()["error"] == "conflict"


def test_short_password_is_rejected(api: TestClient) -> None:
    response = api.post(
        "/api/v1/auth/register",
        json={"email": _email("short"), "password": "short", "full_name": "Ada Lovelace"},
    )

    assert response.status_code == 422
    assert response.json()["error"] == "validation_error"


def test_login_success_and_failure(api: TestClient) -> None:
    email = _email("login")
    _register(api, email)

    success = api.post("/api/v1/auth/login", json={"email": email.upper(), "password": PASSWORD})
    failure = api.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password-1"})
    missing = api.post("/api/v1/auth/login", json={"email": _email("missing"), "password": PASSWORD})

    assert success.status_code == 200
    assert success.json()["user"]["email"] == email
    assert failure.status_code == 401
    assert missing.status_code == 401
    assert failure.json()["message"] == missing.json()["message"]
    assert PASSWORD not in failure.text


def test_me_requires_a_valid_token(api: TestClient) -> None:
    anonymous = api.get("/api/v1/auth/me")
    assert anonymous.status_code == 401

    registered = _register(api, _email("me"))
    me = api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {registered['access_token']}"})

    assert me.status_code == 200
    assert me.json()["email"] == registered["user"]["email"]


def test_logout_invalidates_the_access_token(api: TestClient) -> None:
    registered = _register(api, _email("logout"))
    headers = {"Authorization": f"Bearer {registered['access_token']}"}

    logout = api.post("/api/v1/auth/logout", headers=headers)
    reused = api.get("/api/v1/auth/me", headers=headers)
    fresh = api.post(
        "/api/v1/auth/login",
        json={"email": registered["user"]["email"], "password": PASSWORD},
    )

    assert logout.status_code == 204
    assert reused.status_code == 401
    assert fresh.status_code == 200
    assert api.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fresh.json()['access_token']}"}).status_code == 200


def test_inactive_user_cannot_log_in(api: TestClient, db_session: Session) -> None:
    email = _email("inactive")
    _register(api, email)
    user = db_session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_active = False
    db_session.commit()

    response = api.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid email or password"
