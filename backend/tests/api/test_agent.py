"""The gift agent end to end: real database, catalog and rulebook; a scripted LLM."""

import re
from collections.abc import AsyncIterator, Callable
from datetime import date, timedelta
from typing import Any

import pytest
from httpx import AsyncClient

from giftai.agent.outputs import GiftPicks, PickedGift, TurnAnalysis
from giftai.llm.base import LlmMessage
from giftai.llm.dependencies import get_chat_model
from pipelines.catalog import steps as catalog_steps
from pipelines.catalog.config import SelectionRules
from pipelines.catalog.neighbors import AlsParameters
from pipelines.catalog.workspace import Workspace
from pipelines.rulebook import steps as rulebook_steps
from tests.api.conftest import Headers, create_recipient
from tests.auth_helpers import TokenIssuer
from tests.catalog_samples import CATEGORY, COFFEE, write_sample_dataset
from tests.conftest import build_test_app, make_settings, open_client
from tests.fakes import HashingTextEmbedder, ScriptedChatModel
from tests.rulebook_samples import write_rulebook

FAREWELL = date.today() + timedelta(days=30)


@pytest.fixture(scope="module")
def catalog_and_rules(test_database_url: str, tmp_path_factory: pytest.TempPathFactory) -> None:
    workspace = Workspace(tmp_path_factory.mktemp("catalog"))
    write_sample_dataset(workspace)
    catalog_steps.select(workspace, [CATEGORY], SelectionRules())
    catalog_steps.embed(workspace, HashingTextEmbedder())
    catalog_steps.neighbors(
        workspace, [CATEGORY], AlsParameters(factors=2, iterations=20, neighbors_per_product=4)
    )
    catalog_steps.load(workspace, test_database_url)
    rulebook = write_rulebook(tmp_path_factory.mktemp("rulebook") / "rulebook.yaml")
    rulebook_steps.seed(rulebook, test_database_url)


def analysis(**fields: Any) -> TurnAnalysis:
    values: dict[str, Any] = {
        "recipient_name": None,
        "relationship": None,
        "occasion": None,
        "occasion_date": None,
        "budget_min_usd": None,
        "budget_max_usd": None,
        "interests": [],
        "personality": None,
        "avoid": [],
        "wants_suggestions_now": False,
        "search_queries": [],
        "next_question": None,
    }
    return TurnAnalysis(**(values | fields))


def first_turn(_: str, __: list[LlmMessage]) -> TurnAnalysis:
    return analysis(relationship="coworker", next_question="What does she enjoy?")


def second_turn(_: str, __: list[LlmMessage]) -> TurnAnalysis:
    return analysis(
        recipient_name="Priya",
        relationship="coworker",
        occasion="farewell",
        occasion_date=FAREWELL.isoformat(),
        budget_min_usd=15,
        budget_max_usd=30,
        interests=["coffee"],
        search_queries=["coffee kit", "coffee grinder"],
    )


def pick_coffee(system: str, _: list[LlmMessage]) -> GiftPicks:
    offered = re.findall(r'"asin": "(\w+)"', system)
    coffee = [asin for asin in offered if asin in COFFEE]
    picks = [
        PickedGift(asin=asin, why=f"She loves coffee ({asin}).", rule_ids=["R-001", "R-999"])
        for asin in coffee[:4]
    ]
    # Made-up products are dropped.
    picks.append(PickedGift(asin="B0NOTREAL1", why="Invented.", rule_ids=[]))
    return GiftPicks(intro="Here are a few ideas for Priya.", picks=picks)


class AgentClient:
    def __init__(self, client: AsyncClient, model: ScriptedChatModel) -> None:
        self.client = client
        self.model = model


@pytest.fixture
async def agent(
    catalog_and_rules: None, test_database_url: str, token_issuer: TokenIssuer
) -> AsyncIterator[AgentClient]:
    model = ScriptedChatModel({TurnAnalysis: first_turn, GiftPicks: pick_coffee})
    app = build_test_app(
        make_settings(test_database_url, agent_turns_per_user_per_day=3), token_issuer
    )
    app.dependency_overrides[get_chat_model] = lambda: model
    async with open_client(app) as client:
        yield AgentClient(client, model)


@pytest.fixture
def user(new_user: Callable[[], Headers]) -> Headers:
    return new_user()


async def send(agent: AgentClient, headers: Headers, chat_id: str, text: str) -> dict[str, Any]:
    response = await agent.client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": text}, headers=headers
    )
    assert response.status_code == 201, response.text
    turn: dict[str, Any] = response.json()
    return turn


async def new_chat(agent: AgentClient, headers: Headers, **fields: object) -> str:
    response = await agent.client.post("/api/v1/chats", json=fields, headers=headers)
    assert response.status_code == 201, response.text
    chat_id: str = response.json()["id"]
    return chat_id


async def test_the_agent_asks_first_then_suggests_gifts_that_follow_the_rules(
    agent: AgentClient, user: Headers
) -> None:
    chat_id = await new_chat(agent, user)

    asked = await send(agent, user, chat_id, "I need a gift for a coworker")

    assert asked["reply"]["content"] == "What does she enjoy?"
    assert asked["recommendations"] == []
    assert asked["chat"]["title"] == "New gift idea"

    agent.model.answers[TurnAnalysis] = second_turn
    suggested = await send(agent, user, chat_id, "Priya loves coffee, $15-30, farewell party")

    picks = suggested["recommendations"]
    # The LLM's four coffee picks come first; the ranking tops the list up to five.
    assert len(picks) == 5
    assert {p["product"]["asin"] for p in picks[:4]} <= set(COFFEE)
    assert [p["rank"] for p in picks] == list(range(1, len(picks) + 1))
    assert "B0NOTREAL1" not in {p["product"]["asin"] for p in picks}
    # Only rules that applied to a coworker's farewell are cited; R-999 doesn't exist.
    assert picks[0]["rules"] == [
        {
            "id": "R-001",
            "kind": "do",
            "rule": "Prefer a gift the recipient asked for over a surprise.",
        }
    ]
    assert picks[0]["add_to_cart_url"].endswith(
        f"ASIN.1={picks[0]['product']['asin']}&Quantity.1=1"
    )
    assert suggested["add_all_to_cart_url"].count("ASIN.") == len(picks)
    assert suggested["order_by"] == (FAREWELL - timedelta(days=7)).isoformat()
    assert suggested["reply"]["content"].startswith("Here are a few ideas for Priya.")
    assert "Order by" in suggested["reply"]["content"]

    chat = suggested["chat"]
    assert (chat["occasion"], chat["budget_min_usd"], chat["budget_max_usd"]) == (
        "farewell",
        15,
        30,
    )
    assert chat["title"] == f"Priya, farewell, {FAREWELL:%b} {FAREWELL.day}"

    # The second LLM call saw the rules for a coworker's farewell on that budget.
    pick_prompt = agent.model.calls[-1][1]
    assert "R-002" in pick_prompt and "R-003" in pick_prompt and "R-004" not in pick_prompt

    latest = await agent.client.get(f"/api/v1/chats/{chat_id}/recommendations", headers=user)
    assert [p["product"]["asin"] for p in latest.json()["items"]] == [
        p["product"]["asin"] for p in picks
    ]
    messages = await agent.client.get(f"/api/v1/chats/{chat_id}/messages", headers=user)
    assert [m["role"] for m in messages.json()["items"]] == ["assistant", "user"] * 2


async def test_a_saved_person_starts_the_agent_informed(agent: AgentClient, user: Headers) -> None:
    mom = await create_recipient(agent.client, user, interests=["coffee"])
    chat_id = await new_chat(agent, user, recipient_id=mom["id"], budget_max_usd=30)
    agent.model.answers[TurnAnalysis] = lambda _, __: analysis(
        occasion="birthday", search_queries=["coffee"]
    )

    turn = await send(agent, user, chat_id, "Her birthday is coming up")

    # Relationship and interests came from the saved person, budget from the chat.
    assert turn["recommendations"]
    understand_prompt = agent.model.calls[0][1]
    assert '"relationship":"parent"' in understand_prompt
    assert '"budget_max_usd":30' in understand_prompt
    assert turn["chat"]["title"] == "Mom, birthday"


async def test_each_user_has_a_daily_reply_cap(agent: AgentClient, user: Headers) -> None:
    chat_id = await new_chat(agent, user)
    agent.model.answers[TurnAnalysis] = lambda _, __: analysis(
        next_question="Tell me more?", search_queries=["coffee"]
    )
    for _ in range(3):
        assert (await send(agent, user, chat_id, "hmm"))["recommendations"] == []
    # The daily cap in this app is 3 replies.
    capped = await agent.client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": "hmm"}, headers=user
    )
    assert capped.status_code == 429
    assert capped.json()["error"]["code"] == "rate_limited"
    assert int(capped.headers["Retry-After"]) > 0


async def test_asking_for_ideas_skips_the_questions(agent: AgentClient, user: Headers) -> None:
    chat_id = await new_chat(agent, user)
    agent.model.answers[TurnAnalysis] = lambda _, __: analysis(
        wants_suggestions_now=True, search_queries=["coffee"]
    )

    turn = await send(agent, user, chat_id, "Just show me something")

    assert len(turn["recommendations"]) >= 3


async def test_a_busy_llm_saves_nothing(agent: AgentClient, user: Headers) -> None:
    chat_id = await new_chat(agent, user)
    agent.model.unavailable = True

    response = await agent.client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": "hello"}, headers=user
    )

    assert response.status_code == 503
    assert "send your message again" in response.json()["error"]["message"]
    messages = await agent.client.get(f"/api/v1/chats/{chat_id}/messages", headers=user)
    assert messages.json()["items"] == []


async def test_other_users_chats_are_off_limits(
    agent: AgentClient, user: Headers, new_user: Callable[[], Headers]
) -> None:
    chat_id = await new_chat(agent, user)
    stranger = new_user()

    sent = await agent.client.post(
        f"/api/v1/chats/{chat_id}/messages", json={"content": "hi"}, headers=stranger
    )
    picks = await agent.client.get(f"/api/v1/chats/{chat_id}/recommendations", headers=stranger)

    assert (sent.status_code, picks.status_code) == (404, 404)
    assert agent.model.calls == []
