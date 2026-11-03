import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps, UuidPrimaryKey
from giftai.db.types import string_enum
from giftai.gifting import Occasion


class Chat(UuidPrimaryKey, Timestamps, Base):
    """One gifting task: one recipient, one occasion."""

    __tablename__ = "chats"
    __table_args__ = (
        CheckConstraint(
            "budget_min_usd IS NULL OR budget_max_usd IS NULL OR budget_min_usd <= budget_max_usd",
            name="budget_range_ordered",
        ),
        # Serves the sidebar: a user's chats, most recently active first.
        Index("ix_chats_user_id_updated_at", "user_id", "updated_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # Deleting a saved person deletes the chats about them, as the privacy note promises.
    recipient_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("recipients.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120))
    # False while the title is generated from the chat's details and kept in sync with them.
    title_is_custom: Mapped[bool] = mapped_column(default=False)
    occasion: Mapped[Occasion | None] = mapped_column(string_enum(Occasion))
    occasion_date: Mapped[date | None] = mapped_column(Date)
    budget_min_usd: Mapped[int | None]
    budget_max_usd: Mapped[int | None]


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(UuidPrimaryKey, Base):
    """One turn of a chat, kept for display; the agent keeps its own working state."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_chat_id_created_at", "chat_id", "created_at"),)

    chat_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"))
    role: Mapped[MessageRole] = mapped_column(string_enum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
