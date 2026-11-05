"""Add feedback and availability votes.

feedback_events logs what users do with each pick (opened on Amazon, added to the cart,
thumbs up or down) for the learned ranker; recommendations keep the current thumbs in
rating. availability_votes holds one found / not-found vote per user per product, which
weights the ranking.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-05 06:55:53.676499
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "availability_votes",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("product_asin", sa.String(length=10), nullable=False),
        sa.Column("found", sa.Boolean(), nullable=False),
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
            ["product_asin"],
            ["products.asin"],
            name=op.f("fk_availability_votes_product_asin_products"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_availability_votes_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", "product_asin", name=op.f("pk_availability_votes")),
    )
    op.create_index(
        op.f("ix_availability_votes_product_asin"),
        "availability_votes",
        ["product_asin"],
        unique=False,
    )
    op.create_table(
        "feedback_events",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recommendation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "clicked",
                "added_to_cart",
                "thumbs_up",
                "thumbs_down",
                "rating_cleared",
                name="feedbackkind",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["recommendation_id"],
            ["recommendations.id"],
            name=op.f("fk_feedback_events_recommendation_id_recommendations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_feedback_events_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_feedback_events")),
    )
    op.create_index(
        "ix_feedback_events_recommendation_id_kind",
        "feedback_events",
        ["recommendation_id", "kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_feedback_events_user_id"), "feedback_events", ["user_id"], unique=False
    )
    op.add_column("recommendations", sa.Column("rating", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        op.f("ck_recommendations_rating_is_up_or_down"), "recommendations", "rating IN (-1, 1)"
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_recommendations_rating_is_up_or_down"), "recommendations", type_="check"
    )
    op.drop_column("recommendations", "rating")
    op.drop_index(op.f("ix_feedback_events_user_id"), table_name="feedback_events")
    op.drop_index("ix_feedback_events_recommendation_id_kind", table_name="feedback_events")
    op.drop_table("feedback_events")
    op.drop_index(op.f("ix_availability_votes_product_asin"), table_name="availability_votes")
    op.drop_table("availability_votes")
