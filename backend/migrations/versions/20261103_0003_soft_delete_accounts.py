"""Soft-delete accounts.

Users get their own id, separate from the Supabase user id (now ``auth_user_id``), so a
deleted account can be kept while the same person signs up again. A partial unique index
allows one active account per sign-in. Existing rows were keyed by the Supabase id, so
that id is copied into ``auth_user_id``.

Downgrading drops the link between accounts and sign-ins; use it only in development.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 16:34:30.837704
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("auth_user_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE users SET auth_user_id = id")
    op.alter_column("users", "auth_user_id", nullable=False)
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "uq_users_auth_user_id_active",
        "users",
        ["auth_user_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_users_auth_user_id_active",
        table_name="users",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "auth_user_id")
