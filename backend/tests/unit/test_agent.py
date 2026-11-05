"""The agent's decisions that don't need a database or an LLM."""

from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest
from pydantic import BaseModel

from giftai.agent.graph import (
    TurnState,
    compose_reply,
    merge_profile,
    order_by_advice,
    order_by_date,
    ready_to_suggest,
    search_queries,
    validate_picks,
)
from giftai.agent.outputs import PickedGift, TurnAnalysis
from giftai.agent.profile import MAX_QUESTIONS, GiftProfile
from giftai.agent.ranking import ALREADY_SHOWN_PENALTY, Candidate, price_fit, rank
from giftai.agent.service import apply_profile, profile_for
from giftai.catalog.links import add_to_cart_url
from giftai.catalog.models import Product
from giftai.chats.models import Chat
from giftai.core.config import LlmSettings
from giftai.feedback.availability import AvailabilityStatus, VoteCounts
from giftai.gifting import Occasion, Relationship
from giftai.llm.base import LlmMessage, LlmUnavailableError
from giftai.llm.fallback import FallbackChatModel
from giftai.llm.groq import GroqChatModel
from giftai.recipients.models import Recipient
from giftai.rulebook.models import GiftingRule, RuleKind
from tests.fakes import ScriptedChatModel

TODAY = date(2026, 11, 4)


def product(asin: str, price: str = "25", category: str = "Mugs", **fields: Any) -> Product:
    values: dict[str, Any] = {
        "asin": asin,
        "title": f"Product {asin}",
        "main_category": "Home",
        "category_path": ["Home", category],
        "price_2023": Decimal(price),
        "rating_average": 4.5,
        "rating_count": 1000,
        "image_url": "https://example.com/i.jpg",
        "last_reviewed_on": date(2023, 6, 1),
    }
    return Product(**(values | fields))


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


# Profile


def test_the_llm_adds_to_the_profile_but_never_erases_it() -> None:
    before = GiftProfile(relationship=Relationship.FRIEND, interests=["hiking"], budget_max_usd=50)

    after = merge_profile(
        before,
        analysis(occasion="birthday", occasion_date="2026-12-01", budget_min_usd=20),
    )

    assert after.relationship is Relationship.FRIEND
    assert after.interests == ["hiking"]
    assert (after.occasion, after.occasion_date) == (Occasion.BIRTHDAY, date(2026, 12, 1))
    assert after.budget_range() == (20, 50)


def test_bad_values_from_the_llm_are_ignored() -> None:
    before = GiftProfile(occasion_date=date(2026, 12, 1))

    after = merge_profile(before, analysis(occasion_date="next Friday", budget_max_usd=-5))

    assert after.occasion_date == date(2026, 12, 1)
    assert after.budget_max_usd is None


def test_what_is_missing_comes_most_important_first() -> None:
    assert GiftProfile().missing()[:2] == [
        "what they are into (interests, hobbies or personality)",
        "the budget",
    ]
    assert (
        GiftProfile(
            interests=["tea"],
            budget_max_usd=30,
            relationship=Relationship.FRIEND,
            occasion=Occasion.BIRTHDAY,
        ).missing()
        == []
    )


def state(profile: GiftProfile, asked: int, wants_now: bool = False) -> TurnState:
    return {
        "profile": profile,
        "questions_asked": asked,
        "analysis": analysis(wants_suggestions_now=wants_now),
    }


@pytest.mark.parametrize(
    ("profile", "asked", "wants_now", "ready"),
    [
        (GiftProfile(), 0, False, False),
        (GiftProfile(), 0, True, True),
        (GiftProfile(), MAX_QUESTIONS, False, True),
        # Interests and budget are enough once a couple of questions are in.
        (GiftProfile(interests=["tea"], budget_max_usd=30), 1, False, False),
        (GiftProfile(interests=["tea"], budget_max_usd=30), 2, False, True),
        (
            GiftProfile(
                interests=["tea"],
                budget_max_usd=30,
                relationship=Relationship.FRIEND,
                occasion=Occasion.BIRTHDAY,
            ),
            0,
            False,
            True,
        ),
    ],
)
def test_when_the_agent_stops_asking(
    profile: GiftProfile, asked: int, wants_now: bool, ready: bool
) -> None:
    assert ready_to_suggest(state(profile, asked, wants_now)) is ready


def test_search_queries_fall_back_to_interests() -> None:
    profile = GiftProfile(interests=["tea", "jazz"])

    assert search_queries(analysis(search_queries=[" ", "loose leaf tea set"]), profile) == [
        "loose leaf tea set"
    ]
    assert search_queries(analysis(), profile) == ["tea gift", "jazz gift"]
    assert search_queries(analysis(), GiftProfile()) == ["thoughtful gift"]


def test_the_chat_and_saved_person_override_the_agents_notes() -> None:
    chat = Chat(
        occasion=Occasion.WEDDING,
        budget_max_usd=80,
        agent_profile={"interests": ["baking"], "budget_max_usd": 40, "occasion": "birthday"},
    )
    mom = Recipient(
        name="Mom", relationship=Relationship.PARENT, interests=["gardening"], notes="Calm"
    )

    profile = profile_for(chat, mom)

    assert profile.occasion is Occasion.WEDDING
    assert profile.budget_max_usd == 80
    assert profile.relationship is Relationship.PARENT
    assert profile.interests == ["gardening", "baking"]
    assert profile.personality == "Calm"


def test_what_the_agent_learns_lands_on_the_chat() -> None:
    chat = Chat(title="New gift idea", title_is_custom=False, agent_profile={})
    profile = GiftProfile(
        recipient_name="Sam",
        occasion=Occasion.GRADUATION,
        occasion_date=date(2026, 6, 5),
        budget_min_usd=60,
        budget_max_usd=40,
        interests=["chess"],
    )

    apply_profile(chat, profile, None)

    assert (chat.budget_min_usd, chat.budget_max_usd) == (40, 60)
    assert chat.title == "Sam, graduation, Jun 5"
    assert chat.agent_profile["interests"] == ["chess"]


# Ranking


def test_price_fit_is_full_inside_the_budget_and_fades_outside() -> None:
    assert price_fit(Decimal("30"), 20, 40) == 1.0
    assert 0.4 < price_fit(Decimal("50"), 20, 40) < 0.6
    assert price_fit(Decimal("80"), 20, 40) < 0.1
    assert price_fit(Decimal("80"), None, None) == 1.0


def test_ranking_prefers_relevant_in_budget_products_and_keeps_variety() -> None:
    candidates = [
        Candidate(product(f"B00000MUG{i}", category="Mugs"), relevance=0.9) for i in range(5)
    ]
    candidates.append(Candidate(product("B000000TEA", category="Tea"), relevance=0.6))
    candidates.append(Candidate(product("B000PRICEY", price="400", category="Kettles"), 0.95))

    shortlist = rank(candidates, (20, 40), already_shown=set(), limit=5)

    asins = [c.product.asin for c in shortlist]
    # Three mugs, then other kinds of gift before more mugs; the pricey kettle is last.
    assert asins == ["B00000MUG0", "B00000MUG1", "B00000MUG2", "B000000TEA", "B000PRICEY"]


def test_variety_gives_way_when_few_categories_match() -> None:
    candidates = [Candidate(product(f"B00000MUG{i}"), relevance=0.9) for i in range(5)]

    assert len(rank(candidates, (None, None), already_shown=set(), limit=4)) == 4


def test_products_already_shown_drop_back() -> None:
    first, second = product("B000FIRST1"), product("B000SECOND")
    shortlist = rank(
        [Candidate(first, 0.8), Candidate(second, 0.75)], (None, None), already_shown={"B000FIRST1"}
    )

    assert [c.product.asin for c in shortlist] == ["B000SECOND", "B000FIRST1"]
    assert shortlist[0].score - shortlist[1].score < ALREADY_SHOWN_PENALTY


def test_products_people_could_not_find_sink_but_stay() -> None:
    gone, available = product("B0000GONE1"), product("B000THERE1")
    likely_gone = Candidate(gone, 0.9, availability=AvailabilityStatus.LIKELY_GONE)

    shortlist = rank([likely_gone, Candidate(available, 0.6)], (None, None), already_shown=set())

    assert [c.product.asin for c in shortlist] == ["B000THERE1", "B0000GONE1"]


@pytest.mark.parametrize(
    ("found", "not_found", "status"),
    [
        (0, 0, AvailabilityStatus.UNVERIFIED),
        (2, 1, AvailabilityStatus.VERIFIED),
        (1, 2, AvailabilityStatus.LIKELY_GONE),
        (1, 1, AvailabilityStatus.UNVERIFIED),
    ],
)
def test_the_majority_of_votes_sets_availability(
    found: int, not_found: int, status: AvailabilityStatus
) -> None:
    assert VoteCounts(found, not_found).status is status


# Picks and the reply


def rule(rule_id: str) -> GiftingRule:
    return GiftingRule(id=rule_id, rule="A rule.", rationale="Why.", kind=RuleKind.DO)


def test_picks_must_come_from_the_shortlist_and_cite_offered_rules() -> None:
    shortlist = [Candidate(product(f"B00000000{i}"), 0.9 - i / 10) for i in range(8)]
    picked = [
        PickedGift(asin="B000000003", why="Fits.", rule_ids=["R-001", "R-777", "nonsense"]),
        PickedGift(asin="B000000003", why="Duplicate.", rule_ids=[]),
        PickedGift(asin="B0INVENTED", why="Made up.", rule_ids=[]),
    ]

    picks = validate_picks(picked, shortlist, [rule("R-001")])

    assert [p.candidate.product.asin for p in picks] == [
        "B000000003",
        "B000000000",
        "B000000001",
        "B000000002",
        "B000000004",
    ]
    assert picks[0].rule_ids == ["R-001"]
    assert picks[1].rule_ids == []


def test_order_by_date_allows_a_week_for_shipping() -> None:
    assert order_by_date(date(2026, 12, 1), TODAY) == date(2026, 11, 24)
    assert order_by_date(date(2026, 11, 7), TODAY) == TODAY
    assert order_by_date(date(2026, 11, 1), TODAY) is None
    assert order_by_advice(date(2026, 12, 1), TODAY) == (
        "Order by Tuesday, November 24 so it arrives in time for December 1."
    )
    assert order_by_advice(date(2026, 11, 5), TODAY) == (
        "The day is tomorrow, so order now and choose the fastest shipping."
    )


def test_the_stored_reply_lists_the_picks() -> None:
    shortlist = [Candidate(product("B000000001", price="24.60"), 0.9)]
    picks = validate_picks(
        [PickedGift(asin="B000000001", why="Great.", rule_ids=[])], shortlist, []
    )

    reply = compose_reply("Ideas!", picks, GiftProfile(), TODAY)

    assert reply == "Ideas!\n\n1. Product B000000001 (about $25): Great."


def test_the_cart_link_carries_every_asin() -> None:
    assert add_to_cart_url(["B000000001", "B000000002"]) == (
        "https://www.amazon.com/gp/aws/cart/add.html"
        "?ASIN.1=B000000001&Quantity.1=1&ASIN.2=B000000002&Quantity.2=1"
    )


# LLM providers


class Answer(BaseModel):
    text: str


async def test_the_fallback_model_takes_over_when_the_first_is_busy() -> None:
    busy = ScriptedChatModel({})
    busy.unavailable = True
    backup = ScriptedChatModel({Answer: lambda _, __: Answer(text="from backup")})

    answer = await FallbackChatModel([busy, backup]).generate("s", [], Answer)

    assert answer.text == "from backup"
    assert len(busy.calls) == 1


async def test_the_fallback_model_reports_when_all_are_busy() -> None:
    busy = ScriptedChatModel({})
    busy.unavailable = True

    with pytest.raises(LlmUnavailableError):
        await FallbackChatModel([busy, busy]).generate("s", [], Answer)


async def test_groq_sends_the_schema_and_validates_the_answer() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        content = '{"text": "hello"}'
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    model = GroqChatModel("key", "some-model", transport=httpx.MockTransport(handler))

    answer = await model.generate("Be brief.", [LlmMessage("user", "hi")], Answer)

    assert answer.text == "hello"
    assert seen[0]["model"] == "some-model"
    assert '"text"' in seen[0]["messages"][0]["content"]
    assert seen[0]["messages"][1] == {"role": "user", "content": "hi"}


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(429, json={}),
        httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}),
        httpx.Response(200, json={}),
    ],
)
async def test_groq_failures_are_reported_as_unavailable(response: httpx.Response) -> None:
    model = GroqChatModel("key", "m", transport=httpx.MockTransport(lambda _: response))

    with pytest.raises(LlmUnavailableError):
        await model.generate("s", [], Answer)


def test_blank_keys_in_env_files_mean_no_key() -> None:
    settings = LlmSettings.model_validate({"gemini_api_key": "", "groq_api_key": "  "})

    assert settings.gemini_api_key is None
    assert settings.groq_api_key is None
