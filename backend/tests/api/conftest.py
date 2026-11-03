import uuid
from collections.abc import Callable

import pytest
from httpx import AsyncClient

from tests.auth_helpers import TokenIssuer

# Every API test here needs the real database.
pytestmark = pytest.mark.database

Headers = dict[str, str]


@pytest.fixture
def new_user(token_issuer: TokenIssuer) -> Callable[[], Headers]:
    """Returns auth headers for a brand-new user each call; tests never share accounts."""
    return lambda: token_issuer.headers_for(uuid.uuid4())


@pytest.fixture
def alice(new_user: Callable[[], Headers]) -> Headers:
    return new_user()


@pytest.fixture
def bob(new_user: Callable[[], Headers]) -> Headers:
    return new_user()


async def create_recipient(
    client: AsyncClient, headers: Headers, **fields: object
) -> dict[str, object]:
    body = {"name": "Mom", "relationship": "parent", "interests": ["gardening"]} | fields
    response = await client.post("/api/v1/recipients", json=body, headers=headers)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result


async def create_chat(client: AsyncClient, headers: Headers, **fields: object) -> dict[str, object]:
    response = await client.post("/api/v1/chats", json=fields, headers=headers)
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result
