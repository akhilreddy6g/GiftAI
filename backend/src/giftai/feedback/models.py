import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps, UuidPrimaryKey
from giftai.db.types import string_enum


class FeedbackKind(StrEnum):
    # Opened the product on Amazon.
    CLICKED = "clicked"
    # Used an add-to-cart link that included the product.
    ADDED_TO_CART = "added_to_cart"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    RATING_CLEARED = "rating_cleared"


class FeedbackEvent(UuidPrimaryKey, Base):
    """One thing a user did with a pick. Append-only: the training log for the ranker.
    Being shown is not an event; every ``recommendations`` row already records it.
    """

    __tablename__ = "feedback_events"
    __table_args__ = (
        Index("ix_feedback_events_recommendation_id_kind", "recommendation_id", "kind"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE")
    )
    kind: Mapped[FeedbackKind] = mapped_column(string_enum(FeedbackKind))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AvailabilityVote(Timestamps, Base):
    """Whether one user found the product on Amazon. One vote per user per product; voting
    again replaces it.
    """

    __tablename__ = "availability_votes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # Products are retired rather than deleted, so this stays valid.
    product_asin: Mapped[str] = mapped_column(
        String(10), ForeignKey("products.asin"), primary_key=True, index=True
    )
    found: Mapped[bool] = mapped_column(Boolean)
