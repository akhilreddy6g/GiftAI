import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps, UuidPrimaryKey


class User(UuidPrimaryKey, Timestamps, Base):
    """A GiftAI account, linked to a Supabase sign-in.

    Deleting an account only flags it (``deleted_at``); the row and its data are kept but
    never served again. If the same person signs in later they get a new, empty account,
    so one Supabase sign-in can own several rows, of which at most one is active.
    """

    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_auth_user_id_active",
            "auth_user_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    # The Supabase user id (the token's ``sub`` claim).
    auth_user_id: Mapped[uuid.UUID]
    email: Mapped[str | None] = mapped_column(String(320))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
