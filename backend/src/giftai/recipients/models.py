import uuid

from sqlalchemy import ARRAY, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps, UuidPrimaryKey
from giftai.db.types import string_enum
from giftai.gifting import Relationship


class Recipient(UuidPrimaryKey, Timestamps, Base):
    """Someone a user shops for, saved so later chats about them start informed."""

    __tablename__ = "recipients"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    relationship: Mapped[Relationship] = mapped_column(string_enum(Relationship))
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    notes: Mapped[str | None] = mapped_column(Text)
