import uuid

import pytest
from httpx import AsyncClient

from tests.api.conftest import Headers, create_chat, create_recipient
from tests.auth_helpers import TokenIssuer

pytestmark = pytest.mark.database


async def test_first_request_creates_the_account(
    database_client: AsyncClient, token_issuer: TokenIssuer
) -> None:
    user_id = uuid.uuid4()
    token = token_issuer.issue(user_id, email="new@example.com")

    response = await database_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == str(user_id)
    assert response.json()["email"] == "new@example.com"


async def test_a_changed_email_is_picked_up(
    database_client: AsyncClient, token_issuer: TokenIssuer
) -> None:
    user_id = uuid.uuid4()
    for email in ("old@example.com", "new@example.com"):
        token = token_issuer.issue(user_id, email=email)
        response = await database_client.get(
            "/api/v1/me", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.json()["email"] == "new@example.com"


async def test_deleting_the_account_removes_all_its_data(
    database_client: AsyncClient, alice: Headers
) -> None:
    recipient = await create_recipient(database_client, alice)
    chat = await create_chat(database_client, alice, recipient_id=recipient["id"])

    response = await database_client.delete("/api/v1/me", headers=alice)
    assert response.status_code == 204

    # The next request recreates an empty account for the same sign-in.
    chats = await database_client.get("/api/v1/chats", headers=alice)
    assert chats.json()["items"] == []
    missing = await database_client.get(f"/api/v1/chats/{chat['id']}", headers=alice)
    assert missing.status_code == 404
