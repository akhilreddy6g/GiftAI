from datetime import date
from decimal import Decimal

from pgvector.sqlalchemy import HALFVEC
from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from giftai.db.base import Base, Timestamps
from giftai.embeddings.base import EMBEDDING_DIMENSIONS


class Product(Timestamps, Base):
    """A giftable Amazon US product from the Amazon Reviews 2023 dataset.

    Rows are written only by the offline catalog pipeline. A product dropped from a later
    load stays (recommendations may point at it) with ``in_catalog`` false, out of search.
    """

    __tablename__ = "products"
    __table_args__ = (
        # Cosine distance on half-precision vectors: half the storage of full floats,
        # which keeps about 100,000 products inside the free database.
        Index(
            "ix_products_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "halfvec_cosine_ops"},
        ),
        CheckConstraint("price_2023 > 0", name="price_positive"),
        CheckConstraint("rating_average BETWEEN 1 AND 5", name="rating_in_range"),
    )

    # The dataset's parent ASIN: the product page at amazon.com/dp/<asin>.
    asin: Mapped[str] = mapped_column(String(10), primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    brand: Mapped[str | None] = mapped_column(String(200))
    # The dataset file it came from, such as "Home_and_Kitchen".
    main_category: Mapped[str] = mapped_column(String(60), index=True)
    # Amazon's breadcrumb, such as ["Home & Kitchen", "Kitchen & Dining", "Coffee"].
    category_path: Mapped[list[str]] = mapped_column(ARRAY(String(200)), default=list)
    # Prices are from 2023 and the UI says so; Amazon has the current one.
    price_2023: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rating_average: Mapped[float] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(String(1000))
    short_description: Mapped[str | None] = mapped_column(Text)
    # The newest review in the dataset: recent reviews suggest it's still on sale.
    last_reviewed_on: Mapped[date | None] = mapped_column(Date)
    in_catalog: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    # Deferred: only search needs it, and 384 numbers per row would bloat every read.
    embedding: Mapped[object] = mapped_column(HALFVEC(EMBEDDING_DIMENSIONS), deferred=True)


class ProductNeighbor(Base):
    """ "People who liked this also liked": the top products for each one, from ALS."""

    __tablename__ = "product_neighbors"
    __table_args__ = (UniqueConstraint("product_asin", "neighbor_asin"),)

    product_asin: Mapped[str] = mapped_column(
        ForeignKey("products.asin", ondelete="CASCADE"), primary_key=True
    )
    # 1 is the closest neighbor.
    rank: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    neighbor_asin: Mapped[str] = mapped_column(
        ForeignKey("products.asin", ondelete="CASCADE"), index=True
    )
    # Cosine similarity of the two products' ALS factors.
    score: Mapped[float] = mapped_column(Float)
