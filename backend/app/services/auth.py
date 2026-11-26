from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import User
from app.security import burn_password_check, verify_password

INVALID_LOGIN_MESSAGE = "Invalid username or password"


def authenticate(db: Session, username: str, password: str) -> User:
    """Return the user, or raise 401 with the same message whether the username exists or not."""
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        burn_password_check()
        raise AppError(401, "UNAUTHORIZED", INVALID_LOGIN_MESSAGE)
    if not verify_password(password, user.password_hash):
        raise AppError(401, "UNAUTHORIZED", INVALID_LOGIN_MESSAGE)
    return user
