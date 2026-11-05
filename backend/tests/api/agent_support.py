"""Shared pieces for the agent API tests: a scripted LLM's answers and request helpers."""

import re
from datetime import date, timedelta
from typing import Any

from httpx import AsyncClient

from giftai.agent.outputs import GiftPicks, PickedGift, TurnAnalysis
from giftai.llm.base import LlmMessage
from tests.catalog_samples import COFFEE
from tests.fakes import ScriptedChatModel

Headers = dict[str, str]

FAREWELL = date.today() + timedelta(days=30)


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
