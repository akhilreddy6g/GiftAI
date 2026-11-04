"""The agent's turn as a LangGraph graph:

    understand ──► ask ──────────────► END
              └──► shortlist ──► pick ► END

``understand`` updates the recipient profile from the conversation. If key details are
still missing (and the question budget isn't spent) the agent asks one question;
otherwise it gathers candidates, ranks them, and has the LLM pick and explain 5 or 6
while applying the gifting rules.

The graph holds no state between turns: each turn starts from the chat's stored
messages and profile, so nothing needs a checkpointer or extra database connections.
"""

import logging
import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from giftai.agent.candidates import gather_candidates
from giftai.agent.outputs import GiftPicks, PickedGift, TurnAnalysis
from giftai.agent.profile import MAX_QUESTIONS, GiftProfile
from giftai.agent.prompts import pick_prompt, understand_prompt
from giftai.agent.ranking import Candidate, rank
from giftai.catalog.repository import ProductRepository
from giftai.embeddings.base import TextEmbedder
from giftai.llm.base import ChatModel, LlmMessage
from giftai.rulebook.models import GiftingRule
from giftai.rulebook.retrieval import GiftSituation, KnowledgeRetriever

logger = logging.getLogger(__name__)

MIN_PICKS = 3
MAX_PICKS = 6
MAX_QUERIES = 4
# Shipping time allowed for when working back from the occasion date.
SHIPPING_DAYS = 7
_RULE_ID = re.compile(r"^R-\d{3,6}$")


@dataclass(frozen=True)
class Pick:
    candidate: Candidate
    reason: str
    rule_ids: list[str]


class TurnState(TypedDict, total=False):
    # Inputs
    conversation: list[LlmMessage]
    profile: GiftProfile
    questions_asked: int
    already_shown: set[str]
    today: date
    # Worked out during the turn
    analysis: TurnAnalysis
    shortlist: list[Candidate]
    rules: list[GiftingRule]
    # Outputs
    reply: str
    picks: list[Pick]


@dataclass(frozen=True)
class AgentDependencies:
    model: ChatModel
    products: ProductRepository
    embedder: TextEmbedder
    knowledge: KnowledgeRetriever


def build_agent(
    deps: AgentDependencies,
) -> CompiledStateGraph[TurnState, None, TurnState, TurnState]:
    async def understand(state: TurnState) -> TurnState:
        profile = state["profile"]
        analysis = await deps.model.generate(
            understand_prompt(profile, state["questions_asked"], state["today"]),
            state["conversation"],
            TurnAnalysis,
        )
        return {"analysis": analysis, "profile": merge_profile(profile, analysis)}

    def route(state: TurnState) -> str:
        return "shortlist" if ready_to_suggest(state) else "ask"

    async def ask(state: TurnState) -> TurnState:
        profile = state["profile"]
        question = (state["analysis"].next_question or "").strip()
        if not question:
            gaps = profile.missing()
            question = f"Could you tell me {gaps[0]}?" if gaps else "Anything else I should know?"
        return {"reply": question, "questions_asked": state["questions_asked"] + 1, "picks": []}

    async def shortlist(state: TurnState) -> TurnState:
        profile = state["profile"]
        budget = profile.budget_range()
        rules = list(
            await deps.knowledge.rules_for(
                GiftSituation(profile.relationship, profile.occasion, budget[0], budget[1])
            )
        )
        queries = search_queries(state["analysis"], profile)
        candidates = await gather_candidates(deps.products, deps.embedder, queries, budget)
        return {"shortlist": rank(candidates, budget, state["already_shown"]), "rules": rules}

    def has_shortlist(state: TurnState) -> str:
        return "pick" if len(state["shortlist"]) >= MIN_PICKS else "nothing_found"

    async def nothing_found(state: TurnState) -> TurnState:
        reply = (
            "I couldn't find enough good matches for that yet. Could you widen the budget "
            "or tell me a bit more about what they enjoy?"
        )
        return {"reply": reply, "picks": []}

    async def pick(state: TurnState) -> TurnState:
        profile = state["profile"]
        answer = await deps.model.generate(
            pick_prompt(profile, state["shortlist"], state["rules"]),
            state["conversation"],
            GiftPicks,
        )
        picks = validate_picks(answer.picks, state["shortlist"], state["rules"])
        return {
            "picks": picks,
            "reply": compose_reply(answer.intro, picks, profile, state["today"]),
        }

    graph = StateGraph(TurnState)
    graph.add_node("understand", understand)
    graph.add_node("ask", ask)
    graph.add_node("shortlist", shortlist)
    graph.add_node("nothing_found", nothing_found)
    graph.add_node("pick", pick)
    graph.add_edge(START, "understand")
    graph.add_conditional_edges("understand", route, ["ask", "shortlist"])
    graph.add_conditional_edges("shortlist", has_shortlist, ["pick", "nothing_found"])
    graph.add_edge("ask", END)
    graph.add_edge("nothing_found", END)
    graph.add_edge("pick", END)
    return graph.compile()


def merge_profile(profile: GiftProfile, analysis: TurnAnalysis) -> GiftProfile:
    """The LLM's reading of the whole conversation, over what was known before. A field
    the LLM leaves empty keeps its old value: it only adds or corrects.
    """
    update: dict[str, object] = {}
    for name in ("recipient_name", "relationship", "occasion", "personality"):
        value = getattr(analysis, name)
        if value:
            update[name] = value
    for name in ("budget_min_usd", "budget_max_usd"):
        value = getattr(analysis, name)
        if value is not None and value >= 0:
            update[name] = value
    if analysis.occasion_date:
        try:
            update["occasion_date"] = date.fromisoformat(analysis.occasion_date)
        except ValueError:
            logger.info("Ignoring an unreadable occasion date from the LLM")
    for name in ("interests", "avoid"):
        values = [v.strip()[:80] for v in getattr(analysis, name) if v and v.strip()]
        if values:
            update[name] = list(dict.fromkeys(values))[:20]
    merged = profile.model_dump() | update
    # Validation drops anything malformed back to the previous profile.
    try:
        return GiftProfile.model_validate(merged)
    except ValueError:
        logger.info("Ignoring a profile update that failed validation")
        return profile


def ready_to_suggest(state: TurnState) -> bool:
    profile = state["profile"]
    asked = state["questions_asked"]
    if state["analysis"].wants_suggestions_now or asked >= MAX_QUESTIONS:
        return True
    gaps = profile.missing()
    knows_them = bool(profile.interests or profile.personality)
    has_budget = profile.budget_min_usd is not None or profile.budget_max_usd is not None
    # The essentials are enough after a couple of questions; the rest is nice to have.
    return not gaps or (knows_them and has_budget and asked >= 2)


def search_queries(analysis: TurnAnalysis, profile: GiftProfile) -> list[str]:
    queries = [q.strip()[:120] for q in analysis.search_queries if q and q.strip()]
    if not queries:
        queries = [f"{interest} gift" for interest in profile.interests]
    if not queries and profile.personality:
        queries = [profile.personality[:120]]
    if not queries:
        queries = ["thoughtful gift"]
    return list(dict.fromkeys(queries))[:MAX_QUERIES]


def validate_picks(
    picked: list[PickedGift], shortlist: list[Candidate], rules: list[GiftingRule]
) -> list[Pick]:
    """Keeps only products from the shortlist and rules that were offered; tops up from
    the ranking if the LLM returned too few usable picks.
    """
    by_asin = {candidate.product.asin: candidate for candidate in shortlist}
    rule_ids = {rule.id for rule in rules}
    picks: list[Pick] = []
    for item in picked:
        candidate = by_asin.pop(item.asin.strip(), None)
        if candidate is None:
            continue
        cited = [r for r in dict.fromkeys(item.rule_ids) if _RULE_ID.match(r) and r in rule_ids]
        reason = item.why.strip()[:600] or "A well-reviewed match for what they enjoy."
        picks.append(Pick(candidate, reason, cited))
        if len(picks) == MAX_PICKS:
            return picks
    for candidate in shortlist:
        if len(picks) >= MIN_PICKS + 2:
            break
        if candidate.product.asin in by_asin:
            del by_asin[candidate.product.asin]
            picks.append(Pick(candidate, "A well-reviewed match for what they enjoy.", []))
    return picks


def order_by_date(occasion_date: date | None, today: date) -> date | None:
    """The last day to order with ordinary shipping, or today if that has passed."""
    if occasion_date is None or occasion_date < today:
        return None
    return max(today, occasion_date - timedelta(days=SHIPPING_DAYS))


def order_by_advice(occasion_date: date | None, today: date) -> str | None:
    if occasion_date is None or occasion_date < today:
        return None
    order_by = occasion_date - timedelta(days=SHIPPING_DAYS)
    if today <= order_by:
        return (
            f"Order by {order_by:%A, %B} {order_by.day} so it arrives in time for "
            f"{occasion_date:%B} {occasion_date.day}."
        )
    days = (occasion_date - today).days
    when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
    return f"The day is {when}, so order now and choose the fastest shipping."


def compose_reply(intro: str, picks: list[Pick], profile: GiftProfile, today: date) -> str:
    """The reply as stored in the chat: the agent reads it back next turn, so it lists
    what was suggested.
    """
    items = [
        f"{number}. {p.candidate.product.title[:120]} (about ${p.candidate.product.price_2023:.0f})"
        f": {p.reason}"
        for number, p in enumerate(picks, 1)
    ]
    parts = [intro.strip() or "Here are some ideas I think they'd love.", "\n".join(items)]
    advice = order_by_advice(profile.occasion_date, today)
    if advice:
        parts.append(advice)
    return "\n\n".join(parts)
