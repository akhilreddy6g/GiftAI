"""What the agent tells the LLM. User text is always passed as conversation messages,
never pasted into these instructions, and every answer is validated before use.
"""

import json
from collections.abc import Sequence
from datetime import date

from giftai.agent.profile import MAX_QUESTIONS, GiftProfile
from giftai.agent.ranking import Candidate
from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import GiftingRule

_PERSONA = (
    "You are GiftAI, a warm, concise gift-planning assistant for Amazon US shoppers. "
    "You help the user pick a thoughtful gift for one person and one occasion. "
    "Only discuss gift planning; politely steer anything else back to the gift."
)


def understand_prompt(profile: GiftProfile, questions_asked: int, today: date) -> str:
    return f"""{_PERSONA}

Read the conversation and update what we know about the gift. Today is {today.isoformat()}.

What we knew before this message (keep it unless the user changed it):
{profile.model_dump_json(exclude_none=True)}

Rules:
- relationship must be one of: {", ".join(r.value for r in Relationship)}.
- occasion must be one of: {", ".join(o.value for o in Occasion)}.
- Budgets are whole US dollars. "Around $50" means 40 to 60; "under $30" means max 30.
- Return the full, updated lists of interests and things to avoid.
- search_queries: product searches for things this person would love, based on their
  interests and personality, not on the occasion's cliches. Leave it empty if we know
  nothing about them yet.
- next_question: ask about the most important missing detail ({
        ", ".join(profile.missing()) or "nothing is missing"
    }), one question only, in a friendly sentence. You have asked
  {questions_asked} of at most {MAX_QUESTIONS} questions.
"""


def pick_prompt(
    profile: GiftProfile,
    shortlist: Sequence[Candidate],
    rules: Sequence[GiftingRule],
) -> str:
    products = [
        {
            "asin": c.product.asin,
            "title": c.product.title[:160],
            "category": " > ".join(c.product.category_path[-2:]) or c.product.main_category,
            "price_usd_2023": float(c.product.price_2023),
            "rating": round(c.product.rating_average, 1),
            "ratings": c.product.rating_count,
        }
        for c in shortlist
    ]
    rulebook = [{"id": r.id, "kind": r.kind.value, "rule": r.rule} for r in rules]
    return f"""{_PERSONA}

Choose the 5 or 6 best gifts for this person from the shortlist below.

The person: {profile.model_dump_json(exclude_none=True)}

Gifting rules that apply (follow every "do" you can, never break a "dont"):
{json.dumps(rulebook, ensure_ascii=False)}

Shortlist (choose only from these, using the asin exactly):
{json.dumps(products, ensure_ascii=False)}

Rules for your answer:
- Pick different kinds of gifts, not five of the same thing.
- Include one consumable or experience-like gift when one fits.
- For each pick, say in one or two sentences why it suits this person specifically,
  and list the ids of the rules it follows.
- Never invent products, prices or rules.
"""
