"""How the agent asks the knowledge base what applies to a gifting situation.

The agent depends on ``KnowledgeRetriever`` only. Today the rulebook answers by exact
tags; chapter notes found by meaning can join later as another retriever without the
agent changing.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import GiftingRule


@dataclass(frozen=True)
class GiftSituation:
    """What is known so far; any part may still be unknown."""

    relationship: Relationship | None = None
    occasion: Occasion | None = None
    budget_min_usd: int | None = None
    budget_max_usd: int | None = None


class KnowledgeRetriever(Protocol):
    async def rules_for(self, situation: GiftSituation) -> Sequence[GiftingRule]:
        """Active rules that apply to the situation."""
        ...
