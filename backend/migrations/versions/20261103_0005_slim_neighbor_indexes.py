"""Slim the neighbor table's indexes.

Neighbor lists are the catalog's biggest table. Its extra unique constraint and
neighbor index cost more storage than the rows themselves, and at full catalog size
they would push the free 1 GB database over its limit. The primary key stays.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-03 22:48:02.602179
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(op.f("ix_product_neighbors_neighbor_asin"), table_name="product_neighbors")
    op.drop_constraint(
        op.f("uq_product_neighbors_product_asin"), "product_neighbors", type_="unique"
    )


def downgrade() -> None:
    op.create_unique_constraint(
        op.f("uq_product_neighbors_product_asin"),
        "product_neighbors",
        ["product_asin", "neighbor_asin"],
        postgresql_nulls_not_distinct=False,
    )
    op.create_index(
        op.f("ix_product_neighbors_neighbor_asin"),
        "product_neighbors",
        ["neighbor_asin"],
        unique=False,
    )
