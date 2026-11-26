from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = "unit-test-secret-long-enough-for-hs256"


def test_hash_then_verify_accepts_right_password() -> None:
    password_hash = hash_password("hunter2", rounds=4)

    assert password_hash != "hunter2"
    assert verify_password("hunter2", password_hash)


def test_verify_rejects_wrong_password() -> None:
    assert not verify_password("wrong", hash_password("hunter2", rounds=4))


def test_verify_rejects_password_longer_than_bcrypt_limit() -> None:
    assert not verify_password("x" * 73, hash_password("x" * 72, rounds=4))


def test_verify_rejects_malformed_hash() -> None:
    assert not verify_password("hunter2", "not-a-bcrypt-hash")


def test_token_round_trip_keeps_user_and_role() -> None:
    token = create_access_token(42, "admin", SECRET, expire_minutes=5)

    claims = decode_access_token(token, SECRET)

    assert claims.user_id == 42
    assert claims.role == "admin"


def test_token_subject_is_a_string() -> None:
    token = create_access_token(42, "student", SECRET, expire_minutes=5)

    payload = jwt.decode(token, SECRET, algorithms=["HS256"])

    assert payload["sub"] == "42"


def test_expired_token_is_rejected() -> None:
    long_ago = datetime.now(UTC) - timedelta(hours=2)
    token = create_access_token(1, "student", SECRET, expire_minutes=5, now=long_ago)

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SECRET)


def test_token_signed_with_other_secret_is_rejected() -> None:
    token = create_access_token(
        1, "student", "another-secret-that-is-also-long-enough", expire_minutes=5
    )

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SECRET)


def test_token_without_subject_is_rejected() -> None:
    token = jwt.encode({"exp": datetime.now(UTC) + timedelta(minutes=5)}, SECRET, algorithm="HS256")

    with pytest.raises(InvalidTokenError):
        decode_access_token(token, SECRET)


def test_garbage_token_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        decode_access_token("not.a.token", SECRET)
