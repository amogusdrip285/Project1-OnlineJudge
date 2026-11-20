"""Settings read from environment variables (MASTER_PLAN §3.2)."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET_PREFIX = "change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", frozen=True)

    env: str = "development"
    database_url: str = "postgresql://oj:change-me@localhost:5432/oj"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:5173"
    problems_dir: str = "/data/problems"
    max_source_bytes: int = 65536
    submit_cooldown_seconds: int = 5

    @model_validator(mode="after")
    def _require_real_secret_in_production(self) -> "Settings":
        if self.env == "production" and self.jwt_secret.startswith(DEFAULT_JWT_SECRET_PREFIX):
            raise ValueError("JWT_SECRET must be changed from the default in production")
        return self

    @property
    def sqlalchemy_database_url(self) -> str:
        """`postgresql://` URLs (shared with the judge) are pointed at the psycopg 3 driver."""
        prefix = "postgresql://"
        if self.database_url.startswith(prefix):
            return "postgresql+psycopg://" + self.database_url[len(prefix) :]
        return self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
