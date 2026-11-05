"""Shared fixtures.

Unit tests use an app whose database URL points nowhere; nothing connects until a request
actually needs the database. API tests (marked ``database``) run against the real Postgres
named by ``TEST_DATABASE_URL`` and are skipped when it is unset.
"""

import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from giftai.auth.dependencies import get_token_verifier
from giftai.core.config import Environment, Settings, get_database_settings
from giftai.embeddings.dependencies import get_text_embedder
from giftai.llm.dependencies import get_chat_model
from giftai.main import create_app
from tests.auth_helpers import TEST_SUPABASE_URL, TokenIssuer
from tests.fakes import HashingTextEmbedder

BACKEND_ROOT = Path(__file__).resolve().parents[1]
UNREACHABLE_DATABASE_URL = "postgresql://giftai:giftai@127.0.0.1:1/unreachable"


def make_settings(database_url: str = UNREACHABLE_DATABASE_URL, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "environment": Environment.TEST,
        "database_url": database_url,
        "supabase_url": TEST_SUPABASE_URL,
        "cors_allowed_origins": ["http://localhost:4200"],
    }
    return Settings(**(values | overrides))


def build_test_app(settings: Settings, token_issuer: TokenIssuer) -> FastAPI:
    """The real app, trusting tokens from ``token_issuer`` instead of Supabase, and with
    a lightweight embedder instead of the downloaded model.
    """
    app = create_app(settings)
    app.dependency_overrides[get_token_verifier] = lambda: token_issuer.verifier
    app.dependency_overrides[get_text_embedder] = HashingTextEmbedder
    # No real LLM in tests: agent tests install a scripted one.
    app.dependency_overrides[get_chat_model] = lambda: None
    return app


@asynccontextmanager
async def open_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """An HTTP client for ``app`` with its startup and shutdown hooks run around it."""
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client,
    ):
        yield client


@pytest.fixture(scope="session")
def token_issuer() -> TokenIssuer:
    return TokenIssuer()


@pytest.fixture
def offline_app(token_issuer: TokenIssuer) -> FastAPI:
    return build_test_app(make_settings(), token_issuer)


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

    engine = create_engine(make_settings(database_url).sqlalchemy_database_url)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE; CREATE SCHEMA public"))
    engine.dispose()

    # Alembic's env.py reads the URL from settings, exactly as it does in production.
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv("DATABASE_URL", database_url)
        get_database_settings.cache_clear()
        command.upgrade(Config(str(BACKEND_ROOT / "alembic.ini")), "head")
    get_database_settings.cache_clear()
    yield database_url


@pytest.fixture
async def database_client(
    test_database_url: str, token_issuer: TokenIssuer
) -> AsyncIterator[AsyncClient]:
    app = build_test_app(make_settings(test_database_url), token_issuer)
    async with open_client(app) as client:
        yield client
