"""Add the gifting rulebook.

Rules are short do's and don'ts, tagged by relationship, occasion and budget so the agent
can pick exactly the ones that apply. Sources hold only citations of the books and papers
behind them, never their text.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-03 23:51:06.445602
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "gifting_rules",
        sa.Column("id", sa.String(length=10), nullable=False),
        sa.Column("rule", sa.String(length=300), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("do", "dont", name="rulekind", native_enum=False, create_constraint=True),
            nullable=False,
        ),
        sa.Column("relationships", sa.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column("occasions", sa.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column("budget_min_usd", sa.Integer(), nullable=True),
        sa.Column("budget_max_usd", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            name=op.f("ck_gifting_rules_budget_range_ordered"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_gifting_rules")),
    )
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("authors", sa.String(length=300), nullable=False),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column(
            "kind",
            sa.Enum(
                "book",
                "paper",
                "article",
                name="sourcekind",
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
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_knowledge_sources")),
    )
    op.create_table(
        "rule_sources",
        sa.Column("rule_id", sa.String(length=10), nullable=False),
        sa.Column("source_id", sa.String(length=60), nullable=False),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["gifting_rules.id"],
            name=op.f("fk_rule_sources_rule_id_gifting_rules"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["knowledge_sources.id"],
            name=op.f("fk_rule_sources_source_id_knowledge_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("rule_id", "source_id", name=op.f("pk_rule_sources")),
    )
    op.create_index(op.f("ix_rule_sources_source_id"), "rule_sources", ["source_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rule_sources_source_id"), table_name="rule_sources")
    op.drop_table("rule_sources")
    op.drop_table("knowledge_sources")
    op.drop_table("gifting_rules")
