"""Enable the pgvector extension.

Product and knowledge-base embeddings are stored as vectors, so every later migration
that creates a vector column depends on this one.

Revision ID: 0001
Revises:
Create Date: 2026-11-03
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
