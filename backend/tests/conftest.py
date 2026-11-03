"""Shared fixtures.

Unit tests use an app whose database URL points nowhere; nothing connects until a request
actually needs the database. API tests (marked ``database``) run against the real Postgres
named by ``TEST_DATABASE_URL`` and are skipped when it is unset.
"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from giftai.core.config import Environment, Settings, get_settings
from giftai.main import create_app

BACKEND_ROOT = Path(__file__).resolve().parents[1]
UNREACHABLE_DATABASE_URL = "postgresql://giftai:giftai@127.0.0.1:1/unreachable"


def make_settings(database_url: str = UNREACHABLE_DATABASE_URL) -> Settings:
    return Settings(
        environment=Environment.TEST,
        database_url=database_url,  # type: ignore[arg-type]  # pydantic coerces str
        cors_allowed_origins=["http://localhost:4200"],
    )


@asynccontextmanager
async def open_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client for ``app`` with its startup and shutdown hooks run around it."""
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.fixture
def offline_app() -> FastAPI:
    return create_app(make_settings())


@pytest.fixture
async def offline_client(offline_app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with open_client(offline_app) as client:
        yield client


@pytest.fixture(scope="session")
def test_database_url() -> Iterator[str]:
    """A freshly migrated test database. Its schema is wiped first, so never share it."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set")

    settings = make_settings(database_url)
    engine = create_engine(settings.sqlalchemy_database_url)  # psycopg 3 serves sync too
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    engine.dispose()

    # Alembic's env.py reads the URL from settings, exactly as it does in production.
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    try:
        command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), "head")
        yield database_url
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_settings.cache_clear()


@pytest.fixture
async def database_client(test_database_url: str) -> AsyncIterator[AsyncClient]:
    async with open_client(create_app(make_settings(test_database_url))) as client:
        yield client
