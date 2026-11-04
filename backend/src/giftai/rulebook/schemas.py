from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from giftai.core.validation import BudgetDollars
from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import RuleKind, SourceKind


class RulesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relationship: Relationship | None = None
    occasion: Occasion | None = None
    budget_min: BudgetDollars | None = None
    budget_max: BudgetDollars | None = None

    @model_validator(mode="after")
    def _check_budget_range(self) -> Self:
        if (
            self.budget_min is not None
            and self.budget_max is not None
            and self.budget_min > self.budget_max
        ):
            raise ValueError("budget_min can't be more than budget_max")
        return self


class SourceCitation(BaseModel):
    id: str
    title: str
    authors: str
    year: int | None
    kind: SourceKind
    location: str | None


class RuleRead(BaseModel):
    id: str
    rule: str
    rationale: str
    kind: RuleKind
    relationships: list[Relationship]
    occasions: list[Occasion]
    budget_min_usd: int | None
    budget_max_usd: int | None
    is_active: bool
    sources: list[SourceCitation]


class RuleList(BaseModel):
    items: list[RuleRead]
