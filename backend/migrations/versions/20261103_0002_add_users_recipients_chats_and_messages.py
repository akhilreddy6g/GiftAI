"""Add users, recipients, chats and messages.

Users mirror Supabase accounts by id. Deleting a user removes their recipients, chats and
messages; deleting a recipient removes the chats about them.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03 06:21:27.452228
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_table(
        "recipients",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column(
            "relationship",
            sa.Enum(
                "partner",
                "parent",
                "child",
                "sibling",
                "grandparent",
                "relative",
                "friend",
                "coworker",
                "manager",
                "client",
                "teacher",
                "neighbor",
                "other",
                name="relationship",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("interests", sa.ARRAY(sa.String(length=60)), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_recipients_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recipients")),
    )
    op.create_index(op.f("ix_recipients_user_id"), "recipients", ["user_id"], unique=False)
    op.create_table(
        "chats",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("title_is_custom", sa.Boolean(), nullable=False),
        sa.Column(
            "occasion",
            sa.Enum(
                "birthday",
                "anniversary",
                "holiday",
                "wedding",
                "baby",
                "graduation",
                "housewarming",
                "farewell",
                "retirement",
                "thank_you",
                "get_well",
                "just_because",
                "other",
                name="occasion",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("occasion_date", sa.Date(), nullable=True),
        sa.Column("budget_min_usd", sa.Integer(), nullable=True),
        sa.Column("budget_max_usd", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "budget_min_usd IS NULL OR budget_max_usd IS NULL OR budget_min_usd <= budget_max_usd",
            name=op.f("ck_chats_budget_range_ordered"),
        ),
        sa.ForeignKeyConstraint(
            ["recipient_id"],
            ["recipients.id"],
            name=op.f("fk_chats_recipient_id_recipients"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_chats_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chats")),
    )
    op.create_index(op.f("ix_chats_recipient_id"), "chats", ["recipient_id"], unique=False)
    op.create_index("ix_chats_user_id_updated_at", "chats", ["user_id", "updated_at"], unique=False)
    op.create_table(
        "messages",
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "user", "assistant", name="messagerole", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"], ["chats.id"], name=op.f("fk_messages_chat_id_chats"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_chat_id_created_at", "messages", ["chat_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_messages_chat_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_chats_user_id_updated_at", table_name="chats")
    op.drop_index(op.f("ix_chats_recipient_id"), table_name="chats")
    op.drop_table("chats")
    op.drop_index(op.f("ix_recipients_user_id"), table_name="recipients")
    op.drop_table("recipients")
    op.drop_table("users")
