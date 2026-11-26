"""Checks that migrations run on an empty DB and match the SQLAlchemy models.

Needs a disposable Postgres database in TEST_DATABASE_URL (CI sets it). Skipped otherwise.
Locally:  docker compose up -d db
          TEST_DATABASE_URL=postgresql://oj:change-me@localhost:5432/oj_test uv run pytest
(create the oj_test database first: docker compose exec db createdb -U oj oj_test)
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.config import Settings
from app.models import Base

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BACKEND_DIR = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL not set")

MVP_TABLES = {
    "users",
    "contests",
    "problems",
    "contest_problems",
    "testcases",
    "submissions",
    "submission_results",
}


@pytest.fixture
def db_url() -> str:
    return Settings(database_url=TEST_DATABASE_URL).sqlalchemy_database_url


@pytest.fixture
def alembic_config(db_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture
def migrated_db(alembic_config: Config):
    # Starts from empty and leaves the DB at head, because the other DB tests share it.
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    yield


@pytest.mark.usefixtures("migrated_db")
def test_upgrade_creates_all_mvp_tables(db_url: str) -> None:
    engine = create_engine(db_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert tables >= MVP_TABLES


@pytest.mark.usefixtures("migrated_db")
def test_models_match_migrations(db_url: str) -> None:
    engine = create_engine(db_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"Models and migrations differ: {diff}"


def test_downgrade_removes_all_tables(alembic_config: Config, db_url: str) -> None:
    command.upgrade(alembic_config, "head")
    command.downgrade(alembic_config, "base")

    engine = create_engine(db_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
        command.upgrade(alembic_config, "head")  # leave the shared test DB usable

    assert not (MVP_TABLES & tables)
