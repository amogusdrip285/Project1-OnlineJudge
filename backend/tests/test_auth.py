from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.security import create_access_token
from tests.conftest import TEST_JWT_SECRET
from tests.factories import DEFAULT_PASSWORD, auth_header, make_user


def test_login_returns_token_and_user(api: TestClient, db: Session) -> None:
    user = make_user(db, username="alice", full_name="Alice Nguyen")

    response = api.post("/api/auth/login", json={"username": "alice", "password": DEFAULT_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"] == {
        "id": user.id,
        "username": "alice",
        "full_name": "Alice Nguyen",
        "role": "student",
    }


def test_login_token_works_for_me(api: TestClient, db: Session) -> None:
    make_user(db, username="bob")
    token = api.post(
        "/api/auth/login", json={"username": "bob", "password": DEFAULT_PASSWORD}
    ).json()["token"]

    response = api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == "bob"


def test_wrong_password_and_unknown_user_get_same_401(api: TestClient, db: Session) -> None:
    make_user(db, username="carol")

    wrong_password = api.post("/api/auth/login", json={"username": "carol", "password": "nope"})
    unknown_user = api.post("/api/auth/login", json={"username": "nobody", "password": "nope"})

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert wrong_password.json()["error"] == {
        "code": "UNAUTHORIZED",
        "message": "Invalid username or password",
    }


def test_login_rejects_password_over_72_bytes(api: TestClient) -> None:
    response = api.post("/api/auth/login", json={"username": "x", "password": "p" * 73})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_login_rejects_empty_username(api: TestClient) -> None:
    response = api.post("/api/auth/login", json={"username": "", "password": "p"})

    assert response.status_code == 400


def test_me_without_token_is_401_envelope(api: TestClient) -> None:
    response = api.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_with_expired_token_is_401(api: TestClient, db: Session) -> None:
    user = make_user(db)
    old = datetime.now(UTC) - timedelta(days=2)
    token = create_access_token(user.id, user.role, TEST_JWT_SECRET, expire_minutes=60, now=old)

    response = api.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid or expired token"


def test_me_for_deleted_user_is_401(api: TestClient, db: Session) -> None:
    user = make_user(db)
    headers = auth_header(user, TEST_JWT_SECRET)
    db.delete(user)
    db.flush()

    response = api.get("/api/auth/me", headers=headers)

    assert response.status_code == 401


def test_me_with_wrong_scheme_is_401(api: TestClient) -> None:
    response = api.get("/api/auth/me", headers={"Authorization": "Basic abc"})

    assert response.status_code == 401


def test_cors_preflight_allows_frontend_origin(api: TestClient) -> None:
    response = api.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
