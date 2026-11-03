"""Abuse protection that runs before any database work."""

import uuid
from collections.abc import AsyncIterator

from httpx import AsyncClient

from giftai.core.config import Settings
from tests.auth_helpers import TokenIssuer
from tests.conftest import build_test_app, make_settings, open_client

JSON = {"Content-Type": "application/json"}


async def test_api_routes_require_a_token(offline_client: AsyncClient) -> None:
    response = await offline_client.get("/api/v1/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["WWW-Authenticate"] == "Bearer"


async def test_bodies_over_the_declared_limit_are_refused(offline_client: AsyncClient) -> None:
    response = await offline_client.post(
        "/api/v1/recipients",
        content=b"x" * (64 * 1024 + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"


async def test_streamed_bodies_are_counted_too(offline_client: AsyncClient) -> None:
    async def oversized_stream() -> AsyncIterator[bytes]:
        for _ in range(65):
            yield b"x" * 1024

    response = await offline_client.post(
        "/api/v1/recipients",
        content=oversized_stream(),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413


async def test_callers_over_their_budget_are_told_when_to_retry(
    token_issuer: TokenIssuer,
) -> None:
    settings: Settings = make_settings(rate_limit_requests_per_minute=2)
    headers = token_issuer.headers_for(uuid.uuid4())

    async with open_client(build_test_app(settings, token_issuer)) as client:
        # The limit is checked before the account is loaded, so the first requests pass
        # the limiter and then fail on the (deliberately unreachable) database.
        for _ in range(2):
            response = await client.get("/api/v1/me", headers=headers)
            assert response.status_code == 503
        response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert int(response.headers["Retry-After"]) >= 1
