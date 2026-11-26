from typing import Literal

from pydantic import Field, field_validator

from app.schemas import ApiModel
from app.security import MAX_PASSWORD_BYTES

MAX_USERNAME_LENGTH = 50


class LoginRequest(ApiModel):
    username: str = Field(min_length=1, max_length=MAX_USERNAME_LENGTH)
    password: str = Field(min_length=1)

    @field_validator("password")
    @classmethod
    def _password_fits_bcrypt(cls, value: str) -> str:
        if len(value.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
        return value


class UserOut(ApiModel):
    id: int
    username: str
    full_name: str
    role: Literal["student", "admin"]


class LoginResponse(ApiModel):
    token: str
    user: UserOut
