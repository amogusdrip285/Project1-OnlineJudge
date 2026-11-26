from fastapi import APIRouter

from app.deps import AppSettings, AuthUser, DbSession
from app.schemas.auth import LoginRequest, LoginResponse, UserOut
from app.security import create_access_token
from app.services.auth import authenticate

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(body: LoginRequest, db: DbSession, settings: AppSettings) -> LoginResponse:
    user = authenticate(db, body.username, body.password)
    token = create_access_token(
        user.id, user.role, settings.jwt_secret, settings.jwt_expire_minutes
    )
    return LoginResponse(token=token, user=UserOut.model_validate(user))


@router.get("/me")
def me(user: AuthUser) -> UserOut:
    return UserOut.model_validate(user)
