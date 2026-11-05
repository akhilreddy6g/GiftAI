"""Feedback on picks: ratings, clicks and cart adds, and found / not-found votes."""

from collections.abc import Callable
from typing import Any

import psycopg
from httpx import AsyncClient

from giftai.agent.outputs import TurnAnalysis
from tests.api.agent_support import AgentClient, new_chat, second_turn, send
from tests.api.conftest import Headers


async def suggest(agent: AgentClient, headers: Headers) -> tuple[str, dict[str, Any]]:
    chat_id = await new_chat(agent, headers)
    agent.model.answers[TurnAnalysis] = second_turn
    return chat_id, await send(agent, headers, chat_id, "Priya loves coffee, $15-30, farewell")


def events(database_url: str) -> list[tuple[str, str]]:
    with psycopg.connect(database_url) as connection:
        rows = connection.execute(
            "SELECT recommendation_id::text, kind FROM feedback_events ORDER BY created_at"
        ).fetchall()
    return [(row[0], row[1]) for row in rows]


async def picks_in(
    client: AsyncClient, headers: Headers, chat_id: str, *message_ids: str
) -> dict[str, Any]:
    response = await client.get(
        f"/api/v1/chats/{chat_id}/recommendations",
        params=[("message_id", m) for m in message_ids],
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_picks_can_be_read_back_per_reply(agent: AgentClient, user: Headers) -> None:
    chat_id, first = await suggest(agent, user)
    second = await send(agent, user, chat_id, "Any other ideas?")
    first_reply, second_reply = first["reply"]["id"], second["reply"]["id"]

    pick = first["recommendations"][0]
    assert pick["message_id"] == first_reply
    assert pick["rating"] is None
    assert pick["availability"] == {
        "status": "unverified",
        "found_votes": 0,
        "not_found_votes": 0,
        "your_vote": None,
    }

    both = await picks_in(agent.client, user, chat_id, first_reply, second_reply)
    assert [p["message_id"] for p in both["items"]] == [first_reply] * len(
        first["recommendations"]
    ) + [second_reply] * len(second["recommendations"])
    # Picks from different replies don't make one cart.
    assert both["add_all_to_cart_url"] is None

    one = await picks_in(agent.client, user, chat_id, first_reply)
    assert [p["id"] for p in one["items"]] == [p["id"] for p in first["recommendations"]]
    assert one["add_all_to_cart_url"] == first["add_all_to_cart_url"]


async def test_thumbs_up_down_and_clear_are_kept_and_logged(
    agent: AgentClient, user: Headers, test_database_url: str
) -> None:
    chat_id, turn = await suggest(agent, user)
    pick_id = turn["recommendations"][0]["id"]
    rate = f"/api/v1/recommendations/{pick_id}/rating"

    for rating in ["up", "up", "down", None]:
        response = await agent.client.put(rate, json={"rating": rating}, headers=user)
        assert response.status_code == 204, response.text

    # Rating "up" twice logs it once.
    assert [kind for rec, kind in events(test_database_url) if rec == pick_id] == [
        "thumbs_up",
        "thumbs_down",
        "rating_cleared",
    ]
    await agent.client.put(rate, json={"rating": "down"}, headers=user)
    picks = await picks_in(agent.client, user, chat_id, turn["reply"]["id"])
    assert picks["items"][0]["rating"] == "down"


async def test_clicks_and_cart_adds_are_logged_for_the_users_own_picks(
    agent: AgentClient,
    user: Headers,
    new_user: Callable[[], Headers],
    test_database_url: str,
) -> None:
    _, turn = await suggest(agent, user)
    ids = [p["id"] for p in turn["recommendations"]]

    clicked = await agent.client.post(
        "/api/v1/feedback/events",
        json={"kind": "clicked", "recommendation_ids": ids[:1]},
        headers=user,
    )
    added = await agent.client.post(
        "/api/v1/feedback/events",
        json={"kind": "added_to_cart", "recommendation_ids": ids},
        headers=user,
    )
    assert (clicked.status_code, added.status_code) == (204, 204)
    logged = [(rec, kind) for rec, kind in events(test_database_url) if rec in ids]
    assert logged.count((ids[0], "clicked")) == 1
    assert sorted(rec for rec, kind in logged if kind == "added_to_cart") == sorted(ids)

    stranger = new_user()
    theirs = await agent.client.post(
        "/api/v1/feedback/events",
        json={"kind": "clicked", "recommendation_ids": ids},
        headers=stranger,
    )
    rated = await agent.client.put(
        f"/api/v1/recommendations/{ids[0]}/rating", json={"rating": "up"}, headers=stranger
    )
    assert (theirs.status_code, rated.status_code) == (404, 404)

    # Ratings go through their own endpoint.
    wrong_kind = await agent.client.post(
        "/api/v1/feedback/events",
        json={"kind": "thumbs_up", "recommendation_ids": ids},
        headers=user,
    )
    assert wrong_kind.status_code == 422


async def test_votes_decide_whether_a_product_is_likely_gone(
    agent: AgentClient, user: Headers, new_user: Callable[[], Headers]
) -> None:
    chat_id, turn = await suggest(agent, user)
    asin = turn["recommendations"][0]["product"]["asin"]
    vote = f"/api/v1/products/{asin}/availability"

    missing = await agent.client.put(vote, json={"found": False}, headers=user)
    assert missing.status_code == 200, missing.text
    assert missing.json() == {
        "status": "likely_gone",
        "found_votes": 0,
        "not_found_votes": 1,
        "your_vote": False,
    }

    # Voting again replaces the vote rather than adding one.
    changed = await agent.client.put(vote, json={"found": True}, headers=user)
    assert changed.json()["status"] == "verified"
    assert changed.json()["not_found_votes"] == 0

    other = await agent.client.put(vote, json={"found": False}, headers=new_user())
    assert other.json() | {"your_vote": None} == {
        "status": "unverified",
        "found_votes": 1,
        "not_found_votes": 1,
        "your_vote": None,
    }

    picks = await picks_in(agent.client, user, chat_id, turn["reply"]["id"])
    assert picks["items"][0]["availability"]["your_vote"] is True

    unknown = await agent.client.put(
        "/api/v1/products/B0NOTREAL1/availability", json={"found": True}, headers=user
    )
    assert unknown.status_code == 404
