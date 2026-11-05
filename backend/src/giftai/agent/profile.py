"""What the agent knows about the person being shopped for, and what it still needs."""

from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from giftai.gifting import Occasion, Relationship

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]

# The cap from the design: no more than this many questions before suggesting gifts.
MAX_QUESTIONS = 4


class GiftProfile(BaseModel):
    """Built up over the chat. The chat's own columns (occasion, date, budget) and the
    saved recipient are folded in each turn, so edits made outside the chat count too.
    """

    model_config = ConfigDict(extra="ignore")

    recipient_name: str | None = Field(default=None, max_length=80)
    relationship: Relationship | None = None
    occasion: Occasion | None = None
    occasion_date: date | None = None
    budget_min_usd: int | None = Field(default=None, ge=0, le=100_000)
    budget_max_usd: int | None = Field(default=None, ge=0, le=100_000)
    interests: list[ShortText] = Field(default_factory=list, max_length=20)
    personality: str | None = Field(default=None, max_length=300)
    avoid: list[ShortText] = Field(default_factory=list, max_length=20)

    def missing(self) -> list[str]:
        """What is still worth asking about, most important first."""
        gaps: list[str] = []
        if not self.interests and not self.personality:
            gaps.append("what they are into (interests, hobbies or personality)")
        if self.budget_min_usd is None and self.budget_max_usd is None:
            gaps.append("the budget")
        if self.relationship is None:
            gaps.append("how the user knows them")
        if self.occasion is None:
            gaps.append("the occasion")
        return gaps

    def budget_range(self) -> tuple[int | None, int | None]:
        low, high = self.budget_min_usd, self.budget_max_usd
        if low is not None and high is not None and low > high:
            low, high = high, low
        return low, high
