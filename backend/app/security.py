"""Password hashing (bcrypt) and access tokens (JWT, HS256)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import bcrypt
import jwt

JWT_ALGORITHM = "HS256"
BCRYPT_ROUNDS = 12
# bcrypt only looks at the first 72 bytes; bcrypt >= 4.1 raises on longer input.
MAX_PASSWORD_BYTES = 72


@dataclass(frozen=True)
class TokenClaims:
    user_id: int
    role: str


class InvalidTokenError(Exception):
    """The token is missing claims, expired, or not signed with our secret."""


def hash_password(password: str, rounds: int = BCRYPT_ROUNDS) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=rounds)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    encoded = password.encode()
    if len(encoded) > MAX_PASSWORD_BYTES:
        return False
    try:
        return bcrypt.checkpw(encoded, password_hash.encode())
    except ValueError:  # malformed hash in the DB
        return False


@lru_cache
def _dummy_hash() -> str:
    return hash_password("dummy-password-for-timing")


def burn_password_check() -> None:
    """Spend the same time as a real check, so unknown usernames can't be detected by timing."""
    verify_password("not-the-password", _dummy_hash())


def create_access_token(
    user_id: int, role: str, secret: str, expire_minutes: int, now: datetime | None = None
) -> str:
    issued_at = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),  # PyJWT >= 2.10 requires `sub` to be a string
        "role": role,
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=expire_minutes),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret: str) -> TokenClaims:
    try:
        payload = jwt.decode(
            token, secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]}
        )
        return TokenClaims(user_id=int(payload["sub"]), role=str(payload.get("role", "")))
    except (jwt.PyJWTError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc
