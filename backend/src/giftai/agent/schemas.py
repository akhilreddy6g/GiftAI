import uuid
from datetime import date

from pydantic import BaseModel

from giftai.catalog.schemas import ProductRead
from giftai.chats.schemas import ChatRead, MessageRead
from giftai.feedback.schemas import ProductAvailability, Rating
from giftai.rulebook.models import RuleKind


class CitedRule(BaseModel):
    id: str
    kind: RuleKind
    rule: str


class RecommendationRead(BaseModel):
    id: uuid.UUID
    # The assistant reply that presented it.
    message_id: uuid.UUID
    rank: int
    product: ProductRead
    reason: str
    rules: list[CitedRule]
    add_to_cart_url: str
    # The user's thumbs up or down, if any.
    rating: Rating | None
    # Whether people still find it on Amazon, from their votes.
    availability: ProductAvailability


class RecommendationList(BaseModel):
    items: list[RecommendationRead]
    # Adds every pick to the user's Amazon cart at once.
    add_all_to_cart_url: str | None


class ChatTurn(BaseModel):
    """One exchange: the user's message, the agent's reply, and any gift picks."""

    message: MessageRead
    reply: MessageRead
    recommendations: list[RecommendationRead]
    add_all_to_cart_url: str | None
    # Worked back from the occasion date, allowing a week for shipping.
    order_by: date | None
    # The chat as the agent left it: it fills in occasion, date and budget as it learns them.
    chat: ChatRead
