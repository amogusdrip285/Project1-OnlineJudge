"""FastAPI dependencies: the current user and the admin guard."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.errors import AppError
from app.models import User
from app.security import InvalidTokenError, decode_access_token

ADMIN_ROLE = "admin"

_bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    full_name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN_ROLE


def _unauthorized(message: str = "Not authenticated") -> AppError:
    return AppError(401, "UNAUTHORIZED", message)


def get_current_user(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()
    try:
        claims = decode_access_token(credentials.credentials, settings.jwt_secret)
    except InvalidTokenError as exc:
        raise _unauthorized("Invalid or expired token") from exc

    user = db.get(User, claims.user_id)
    if user is None:
        raise _unauthorized("Invalid or expired token")
    return CurrentUser(id=user.id, username=user.username, full_name=user.full_name, role=user.role)


AuthUser = Annotated[CurrentUser, Depends(get_current_user)]


def require_admin(user: AuthUser) -> CurrentUser:
    if not user.is_admin:
        raise AppError(403, "FORBIDDEN", "Admin only")
    return user


AdminUser = Annotated[CurrentUser, Depends(require_admin)]
