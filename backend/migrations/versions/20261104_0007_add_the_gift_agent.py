"""Add the gift agent.

Recommendations keep every pick the agent shows, with its reason and cited rules; they
feed "why this gift" now and the learned ranker later. agent_usage caps each user's
daily share of the free LLM quota. Chats gain the agent's notes on the recipient and a
count of the questions it has asked.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-04 23:24:29.829739
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_usage",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("turns", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_agent_usage_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "day", name=op.f("pk_agent_usage")),
    )
    op.create_table(
        "recommendations",
        sa.Column("chat_id", sa.Uuid(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("product_asin", sa.String(length=10), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("rule_ids", sa.ARRAY(sa.String(length=10)), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            name=op.f("fk_recommendations_chat_id_chats"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
            name=op.f("fk_recommendations_message_id_messages"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_asin"],
            ["products.asin"],
            name=op.f("fk_recommendations_product_asin_products"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendations")),
        sa.UniqueConstraint("message_id", "rank", name=op.f("uq_recommendations_message_id")),
    )
    op.create_index(
        "ix_recommendations_chat_id_created_at",
        "recommendations",
        ["chat_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_recommendations_product_asin"), "recommendations", ["product_asin"], unique=False
    )
    op.add_column(
        "chats",
        sa.Column(
            "agent_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
    )
    op.add_column(
        "chats",
        sa.Column("agent_questions_asked", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chats", "agent_questions_asked")
    op.drop_column("chats", "agent_profile")
    op.drop_index(op.f("ix_recommendations_product_asin"), table_name="recommendations")
    op.drop_index("ix_recommendations_chat_id_created_at", table_name="recommendations")
    op.drop_table("recommendations")
    op.drop_table("agent_usage")
