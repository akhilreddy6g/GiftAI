"""Capitalize existing chat titles.

Titles are now saved in sentence case ("Wedding, Jun 6", not "wedding, Jun 6"). This
brings older chats in line by capitalizing their first letter. Downgrading leaves them
capitalized, since the original case isn't kept.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-05 21:40:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE chats SET title = upper(left(title, 1)) || substr(title, 2) "
        "WHERE left(title, 1) <> upper(left(title, 1))"
    )


def downgrade() -> None:
    pass
