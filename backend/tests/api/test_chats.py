import pytest
from httpx import AsyncClient

from tests.api.conftest import Headers, create_chat, create_recipient

pytestmark = pytest.mark.database


async def test_a_chat_is_titled_from_its_details(
    database_client: AsyncClient, alice: Headers
) -> None:
    mom = await create_recipient(database_client, alice, name="Mom")

    chat = await create_chat(
        database_client,
        alice,
        recipient_id=mom["id"],
        occasion="birthday",
        occasion_date="2026-12-14",
    )

    assert chat["title"] == "Mom, birthday, Dec 14"
    assert chat["title_is_custom"] is False


async def test_the_automatic_title_follows_changes_until_the_user_renames_it(
    database_client: AsyncClient, alice: Headers
) -> None:
    chat = await create_chat(database_client, alice)
    assert chat["title"] == "New gift idea"
    url = f"/api/v1/chats/{chat['id']}"

    retitled = await database_client.patch(url, json={"occasion": "wedding"}, headers=alice)
    assert retitled.json()["title"] == "Wedding"

    lowercase = await database_client.patch(url, json={"title": "jo & Sam"}, headers=alice)
    assert lowercase.json()["title"] == "Jo & Sam"
    renamed = await database_client.patch(url, json={"title": "Jo & Sam"}, headers=alice)
    kept = await database_client.patch(url, json={"occasion": "anniversary"}, headers=alice)
    assert renamed.json()["title"] == kept.json()["title"] == "Jo & Sam"

    reset = await database_client.patch(url, json={"title": None}, headers=alice)
    assert reset.json()["title"] == "Anniversary"
    assert reset.json()["title_is_custom"] is False


async def test_budget_ranges_must_be_ordered(database_client: AsyncClient, alice: Headers) -> None:
    rejected = await database_client.post(
        "/api/v1/chats", json={"budget_min_usd": 80, "budget_max_usd": 20}, headers=alice
    )
    assert rejected.status_code == 422

    chat = await create_chat(database_client, alice, budget_min_usd=20, budget_max_usd=80)
    patched = await database_client.patch(
        f"/api/v1/chats/{chat['id']}", json={"budget_min_usd": 100}, headers=alice
    )
    assert patched.status_code == 400


async def test_chats_cannot_point_at_someone_elses_recipient(
    database_client: AsyncClient, alice: Headers, bob: Headers
) -> None:
    alices_mom = await create_recipient(database_client, alice)

    response = await database_client.post(
        "/api/v1/chats", json={"recipient_id": alices_mom["id"]}, headers=bob
    )

    assert response.status_code == 404


async def test_deleting_a_recipient_deletes_their_chats(
    database_client: AsyncClient, alice: Headers
) -> None:
    mom = await create_recipient(database_client, alice)
    chat = await create_chat(database_client, alice, recipient_id=mom["id"])

    await database_client.delete(f"/api/v1/recipients/{mom['id']}", headers=alice)

    response = await database_client.get(f"/api/v1/chats/{chat['id']}", headers=alice)
    assert response.status_code == 404


async def test_messages_are_stored_and_bump_the_chat(
    database_client: AsyncClient, alice: Headers
) -> None:
    older = await create_chat(database_client, alice)
    await create_chat(database_client, alice)

    sent = await database_client.post(
        f"/api/v1/chats/{older['id']}/messages",
        json={"content": "  Ideas for my mom?  "},
        headers=alice,
    )
    assert sent.status_code == 201
    turn = sent.json()
    assert (turn["message"]["role"], turn["message"]["content"]) == ("user", "Ideas for my mom?")
    # No LLM is configured in tests, so the assistant says it is switched off.
    assert turn["reply"]["role"] == "assistant"
    assert "switched off" in turn["reply"]["content"]
    assert turn["recommendations"] == []

    messages = await database_client.get(f"/api/v1/chats/{older['id']}/messages", headers=alice)
    assert [m["role"] for m in messages.json()["items"]] == ["assistant", "user"]

    chats = await database_client.get("/api/v1/chats", headers=alice)
    assert chats.json()["items"][0]["id"] == older["id"]


async def test_users_cannot_read_or_post_in_each_others_chats(
    database_client: AsyncClient, alice: Headers, bob: Headers
) -> None:
    chat = await create_chat(database_client, alice)
    url = f"/api/v1/chats/{chat['id']}/messages"

    assert (await database_client.get(url, headers=bob)).status_code == 404
    posted = await database_client.post(url, json={"content": "hi"}, headers=bob)
    assert posted.status_code == 404
