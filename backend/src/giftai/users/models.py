import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps


class User(Timestamps, Base):
    """A GiftAI account. Its id is the Supabase user id, so no mapping table is needed."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320))
