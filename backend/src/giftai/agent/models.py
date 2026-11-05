import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from giftai.catalog.models import Product
from giftai.db.base import Base, UuidPrimaryKey


class Recommendation(UuidPrimaryKey, Base):
    """A product the agent suggested in a reply, with its reason and the rules it cites."""

    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("message_id", "rank"),
        Index("ix_recommendations_chat_id_created_at", "chat_id", "created_at"),
        CheckConstraint("rating IN (-1, 1)", name="rating_is_up_or_down"),
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    # The assistant message that presented it.
    message_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    # Products are retired rather than deleted, so this stays valid.
    product_asin: Mapped[str] = mapped_column(ForeignKey("products.asin"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    # Rules are retired rather than deleted too, so the ids keep resolving.
    rule_ids: Mapped[list[str]] = mapped_column(ARRAY(String(10)), default=list)
    score: Mapped[float] = mapped_column(Float)
    # The user's thumbs: 1 up, -1 down, null not rated. Each change is also logged as a
    # feedback event.
    rating: Mapped[int | None] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    product: Mapped[Product] = relationship(lazy="joined")


class AgentUsage(Base):
    """Agent replies per user per day, which caps each user's share of the LLM quota.
    Kept in the database (not memory) so restarts and several instances agree.
    """

    __tablename__ = "agent_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    day: Mapped[date] = mapped_column(Date, primary_key=True)
    turns: Mapped[int] = mapped_column(Integer, default=0)
