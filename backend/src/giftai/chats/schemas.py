import uuid
from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from giftai.chats.models import MessageRole
from giftai.core.validation import BudgetDollars, MessageText, PartialUpdate, Title
from giftai.gifting import Occasion


def _check_budget_order(minimum: int | None, maximum: int | None) -> None:
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("budget_min_usd can't be more than budget_max_usd")


class ChatCreate(BaseModel):
    """Every field is optional: a chat can start empty and the agent fills in details."""

    model_config = ConfigDict(extra="forbid")

    recipient_id: uuid.UUID | None = None
    title: Title | None = None
    occasion: Occasion | None = None
    occasion_date: date | None = None
    budget_min_usd: BudgetDollars | None = None
    budget_max_usd: BudgetDollars | None = None

    @model_validator(mode="after")
    def _budget_range_is_ordered(self) -> Self:
        _check_budget_order(self.budget_min_usd, self.budget_max_usd)
        return self


class ChatUpdate(PartialUpdate):
    """Setting ``title`` to null switches back to the automatic title."""

    recipient_id: uuid.UUID | None = None
    title: Title | None = None
    occasion: Occasion | None = None
    occasion_date: date | None = None
    budget_min_usd: BudgetDollars | None = None
    budget_max_usd: BudgetDollars | None = None


class ChatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_id: uuid.UUID | None
    title: str
    title_is_custom: bool
    occasion: Occasion | None
    occasion_date: date | None
    budget_min_usd: int | None
    budget_max_usd: int | None
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: MessageText


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    created_at: datetime
