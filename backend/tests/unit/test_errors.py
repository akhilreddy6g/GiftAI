"""Every failure, expected or not, reaches the client in the same envelope."""

from collections.abc import AsyncIterator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from giftai.core.errors import NotFoundError
from giftai.main import create_app
from tests.conftest import make_settings, open_client


class _Payload(BaseModel):
    name: str


def _app_with_failing_routes() -> FastAPI:
    app = create_app(make_settings())

    @app.get("/raises-not-found")
    async def raises_not_found() -> None:
        raise NotFoundError("That recipient doesn't exist.")

    @app.get("/crashes")
    async def crashes() -> None:
        raise RuntimeError("secret internal detail")

    @app.post("/validates")
    async def validates(payload: _Payload) -> _Payload:
        return payload

    return app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with open_client(_app_with_failing_routes()) as client:
        yield client


async def test_app_errors_keep_their_status_and_user_message(client: AsyncClient) -> None:
    response = await client.get("/raises-not-found")

    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["message"] == "That recipient doesn't exist."
    assert error["request_id"] == response.headers["X-Request-ID"]


async def test_unexpected_errors_hide_internal_details() -> None:
    # The server re-raises crashes after responding (so they are logged); the transport
    # must not, or the test would see the exception instead of the response.
    transport = ASGITransport(app=_app_with_failing_routes(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/crashes")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret" not in response.text


async def test_validation_errors_name_the_offending_field(client: AsyncClient) -> None:
    response = await client.post("/validates", json={})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["message"].startswith("name:")


async def test_unknown_routes_use_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/no-such-route")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_a_safe_incoming_request_id_is_reused(client: AsyncClient) -> None:
    response = await client.get("/no-such-route", headers={"X-Request-ID": "trace-abc.123"})

    assert response.headers["X-Request-ID"] == "trace-abc.123"


async def test_an_unsafe_incoming_request_id_is_replaced(client: AsyncClient) -> None:
    response = await client.get("/no-such-route", headers={"X-Request-ID": "bad id\nforged"})

    assert response.headers["X-Request-ID"] != "bad id\nforged"
    assert len(response.headers["X-Request-ID"]) == 32
