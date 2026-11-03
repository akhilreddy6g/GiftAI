import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, text

from tests.api.conftest import Headers, create_chat, create_recipient
from tests.auth_helpers import TokenIssuer
from tests.conftest import make_settings

pytestmark = pytest.mark.database


async def test_first_request_creates_the_account(
    database_client: AsyncClient, token_issuer: TokenIssuer
) -> None:
    headers = {"Authorization": f"Bearer {token_issuer.issue(email='new@example.com')}"}

    first = await database_client.get("/api/v1/me", headers=headers)
    second = await database_client.get("/api/v1/me", headers=headers)

    assert first.status_code == 200
    assert first.json()["email"] == "new@example.com"
    assert second.json()["id"] == first.json()["id"]


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


async def test_deleting_the_account_gives_a_fresh_start_and_keeps_the_old_data(
    database_client: AsyncClient, alice: Headers, test_database_url: str
) -> None:
    old_account_id = (await database_client.get("/api/v1/me", headers=alice)).json()["id"]
    await create_recipient(database_client, alice)
    await create_chat(database_client, alice)

    response = await database_client.delete("/api/v1/me", headers=alice)
    assert response.status_code == 204

    # Signing in again starts a new, empty account.
    new_account = await database_client.get("/api/v1/me", headers=alice)
    assert new_account.json()["id"] != old_account_id
    for path in ("/api/v1/chats", "/api/v1/recipients"):
        assert (await database_client.get(path, headers=alice)).json()["items"] == []

    # The old account is only flagged: its rows are still in the database.
    engine = create_engine(make_settings(test_database_url).sqlalchemy_database_url)
    with engine.connect() as connection:
        deleted_at, recipients, chats = connection.execute(
            text(
                "SELECT deleted_at,"
                " (SELECT count(*) FROM recipients WHERE user_id = :id),"
                " (SELECT count(*) FROM chats WHERE user_id = :id)"
                " FROM users WHERE id = :id"
            ),
            {"id": old_account_id},
        ).one()
    engine.dispose()
    assert deleted_at is not None
    assert (recipients, chats) == (1, 1)
