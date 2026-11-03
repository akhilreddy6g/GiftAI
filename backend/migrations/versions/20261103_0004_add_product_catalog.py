"""Add the product catalog and also-liked neighbors.

Products are giftable items from the Amazon Reviews 2023 dataset, each with a
half-precision embedding under an HNSW cosine index for meaning search. Neighbors are the
precomputed "people who liked this also liked" lists from the offline ALS model.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 17:39:08.029290
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("asin", sa.String(length=10), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("brand", sa.String(length=200), nullable=True),
        sa.Column("main_category", sa.String(length=60), nullable=False),
        sa.Column("category_path", sa.ARRAY(sa.String(length=200)), nullable=False),
        sa.Column("price_2023", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("rating_average", sa.Float(), nullable=False),
        sa.Column("rating_count", sa.Integer(), nullable=False),
        sa.Column("image_url", sa.String(length=1000), nullable=False),
        sa.Column("short_description", sa.Text(), nullable=True),
        sa.Column("last_reviewed_on", sa.Date(), nullable=True),
        sa.Column("in_catalog", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("embedding", HALFVEC(dim=384), nullable=False),
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
        sa.CheckConstraint("price_2023 > 0", name=op.f("ck_products_price_positive")),
        sa.CheckConstraint(
            "rating_average BETWEEN 1 AND 5", name=op.f("ck_products_rating_in_range")
        ),
        sa.PrimaryKeyConstraint("asin", name=op.f("pk_products")),
    )
    op.create_index(
        "ix_products_embedding_hnsw",
        "products",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    op.create_index(op.f("ix_products_main_category"), "products", ["main_category"], unique=False)
    op.create_table(
        "product_neighbors",
        sa.Column("product_asin", sa.String(length=10), nullable=False),
        sa.Column("rank", sa.SmallInteger(), nullable=False),
        sa.Column("neighbor_asin", sa.String(length=10), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["neighbor_asin"],
            ["products.asin"],
            name=op.f("fk_product_neighbors_neighbor_asin_products"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_asin"],
            ["products.asin"],
            name=op.f("fk_product_neighbors_product_asin_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("product_asin", "rank", name=op.f("pk_product_neighbors")),
        sa.UniqueConstraint(
            "product_asin", "neighbor_asin", name=op.f("uq_product_neighbors_product_asin")
        ),
    )
    op.create_index(
        op.f("ix_product_neighbors_neighbor_asin"),
        "product_neighbors",
        ["neighbor_asin"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_neighbors_neighbor_asin"), table_name="product_neighbors")
    op.drop_table("product_neighbors")
    op.drop_index(op.f("ix_products_main_category"), table_name="products")
    op.drop_index(
        "ix_products_embedding_hnsw",
        table_name="products",
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "halfvec_cosine_ops"},
    )
    op.drop_table("products")
