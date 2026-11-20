import pytest
from pydantic import ValidationError

from app.config import Settings


def test_plain_postgres_url_uses_psycopg_driver() -> None:
    settings = Settings(database_url="postgresql://oj:pw@db:5432/oj")

    assert settings.sqlalchemy_database_url == "postgresql+psycopg://oj:pw@db:5432/oj"


def test_url_with_explicit_driver_is_kept() -> None:
    settings = Settings(database_url="postgresql+psycopg://oj:pw@db:5432/oj")

    assert settings.sqlalchemy_database_url == "postgresql+psycopg://oj:pw@db:5432/oj"


def test_cors_origins_are_split_on_commas() -> None:
    settings = Settings(cors_origins="http://localhost:5173, http://127.0.0.1:5173")

    assert settings.cors_origin_list == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_production_refuses_default_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET"):
        Settings(env="production", jwt_secret="change-me-to-a-long-random-string")


def test_production_accepts_real_jwt_secret() -> None:
    settings = Settings(env="production", jwt_secret="x" * 40)

    assert settings.env == "production"
