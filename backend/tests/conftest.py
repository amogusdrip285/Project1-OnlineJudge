"""Shared fixtures.

DB tests need a disposable Postgres database in TEST_DATABASE_URL (CI sets it); they are skipped
otherwise. Each test runs inside one transaction that is rolled back at the end, so tests never
see each other's rows. Service code may call `commit()`: it only releases a SAVEPOINT.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_JWT_SECRET = "test-secret-that-is-long-enough-for-hs256"


def db_url_for_tests() -> str:
    return Settings(database_url=TEST_DATABASE_URL or "").sqlalchemy_database_url


def alembic_config_for(db_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", db_url)
    return config


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL or "postgresql://unused@localhost/unused",
        jwt_secret=TEST_JWT_SECRET,
        problems_dir=str(tmp_path / "problems"),
        seed_dir=str(tmp_path / "seed"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    # raise_server_exceptions=False lets tests see the real 500 response body.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    url = db_url_for_tests()
    command.upgrade(alembic_config_for(url), "head")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Iterator[Session]:
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def api(app: FastAPI, db: Session) -> Iterator[TestClient]:
    """A client whose requests use the test transaction."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
