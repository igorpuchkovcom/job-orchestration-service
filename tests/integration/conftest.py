import os
from pathlib import Path
from typing import Iterator

import pytest
from alembic.config import Config
from redis import Redis
from sqlalchemy import text
from sqlalchemy.engine import Engine

from alembic import command
from app.core.config import get_settings
from app.persistence.db import create_engine_from_url, reset_db_state

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _database_url() -> str:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set for integration tests.")
    return database_url


def _redis_url() -> str:
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        raise RuntimeError("REDIS_URL must be set for Redis-backed integration tests.")
    return redis_url


def _reset_database(engine: Engine) -> None:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))


@pytest.fixture
def database_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    value = _database_url()
    monkeypatch.setenv("DATABASE_URL", value)
    get_settings.cache_clear()
    reset_db_state()
    try:
        yield value
    finally:
        get_settings.cache_clear()
        reset_db_state()


@pytest.fixture
def redis_url(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    value = _redis_url()
    monkeypatch.setenv("REDIS_URL", value)
    get_settings.cache_clear()
    reset_db_state()
    try:
        yield value
    finally:
        get_settings.cache_clear()
        reset_db_state()


@pytest.fixture
def clean_redis(redis_url: str) -> Iterator[Redis]:
    client = Redis.from_url(redis_url)
    client.flushdb()
    try:
        yield client
    finally:
        client.flushdb()
        client.close()


@pytest.fixture
def alembic_config(database_url: str) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def database_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine_from_url(database_url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def clean_database_engine(database_engine: Engine) -> Engine:
    _reset_database(database_engine)
    return database_engine


@pytest.fixture
def migrated_engine(clean_database_engine: Engine, alembic_config: Config) -> Engine:
    command.upgrade(alembic_config, "head")
    return clean_database_engine


@pytest.fixture
def viewer_headers() -> dict[str, str]:
    return {
        "X-Demo-Principal": "viewer-user",
        "X-Demo-Role": "viewer",
    }


@pytest.fixture
def operator_headers() -> dict[str, str]:
    return {
        "X-Demo-Principal": "operator-user",
        "X-Demo-Role": "operator",
    }


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return {
        "X-Demo-Principal": "admin-user",
        "X-Demo-Role": "admin",
    }
