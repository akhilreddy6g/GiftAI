"""Writes the catalog and its neighbors into Postgres in one transaction.

Re-running is safe: products are upserted, products missing from the new catalog are
marked out of catalog (never deleted, since recommendations may point at them), and the
neighbor lists are replaced. If anything fails, the database keeps the previous catalog.

Storage matters on the free 1 GB plan, so a reload avoids leaving dead copies behind:
unchanged products aren't rewritten, the neighbor table is truncated rather than deleted
row by row, and a vacuum afterwards lets the next load reuse any freed space.
"""

import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import psycopg

from pipelines.catalog.records import CatalogProduct

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NeighborRow:
    product_asin: str
    rank: int
    neighbor_asin: str
    score: float


@dataclass(frozen=True)
class LoadReport:
    products_loaded: int
    products_retired: int
    neighbor_rows: int
    database_size_mb: float


_STAGE_PRODUCTS = """
CREATE TEMPORARY TABLE staged_products (
    asin varchar(10) PRIMARY KEY,
    title varchar(500) NOT NULL,
    brand varchar(200),
    main_category varchar(60) NOT NULL,
    category_path varchar(200)[] NOT NULL,
    price_2023 numeric(10, 2) NOT NULL,
    rating_average double precision NOT NULL,
    rating_count integer NOT NULL,
    image_url varchar(1000) NOT NULL,
    short_description text,
    last_reviewed_on date,
    embedding halfvec(384) NOT NULL
) ON COMMIT DROP
"""

_PRODUCT_COLUMNS = (
    "asin, title, brand, main_category, category_path, price_2023, rating_average, "
    "rating_count, image_url, short_description, last_reviewed_on, embedding"
)

_UPSERT_PRODUCTS = f"""
INSERT INTO products ({_PRODUCT_COLUMNS}, in_catalog)
SELECT {_PRODUCT_COLUMNS}, true FROM staged_products
ON CONFLICT (asin) DO UPDATE SET
    title = EXCLUDED.title,
    brand = EXCLUDED.brand,
    main_category = EXCLUDED.main_category,
    category_path = EXCLUDED.category_path,
    price_2023 = EXCLUDED.price_2023,
    rating_average = EXCLUDED.rating_average,
    rating_count = EXCLUDED.rating_count,
    image_url = EXCLUDED.image_url,
    short_description = EXCLUDED.short_description,
    last_reviewed_on = EXCLUDED.last_reviewed_on,
    embedding = EXCLUDED.embedding,
    in_catalog = true,
    updated_at = now()
WHERE (
    products.title, products.brand, products.main_category, products.category_path,
    products.price_2023, products.rating_average, products.rating_count, products.image_url,
    products.short_description, products.last_reviewed_on, products.embedding,
    products.in_catalog
) IS DISTINCT FROM (
    EXCLUDED.title, EXCLUDED.brand, EXCLUDED.main_category, EXCLUDED.category_path,
    EXCLUDED.price_2023, EXCLUDED.rating_average, EXCLUDED.rating_count, EXCLUDED.image_url,
    EXCLUDED.short_description, EXCLUDED.last_reviewed_on, EXCLUDED.embedding, true
)
"""  # noqa: S608  # fixed column names, no user input

_RETIRE_MISSING = """
UPDATE products SET in_catalog = false, updated_at = now()
WHERE in_catalog AND NOT EXISTS (SELECT 1 FROM staged_products s WHERE s.asin = products.asin)
"""

_STAGE_NEIGHBORS = """
CREATE TEMPORARY TABLE staged_neighbors (
    product_asin varchar(10) NOT NULL,
    rank smallint NOT NULL,
    neighbor_asin varchar(10) NOT NULL,
    score double precision NOT NULL
) ON COMMIT DROP
"""

_REPLACE_NEIGHBORS = """
INSERT INTO product_neighbors (product_asin, rank, neighbor_asin, score)
SELECT n.product_asin, n.rank, n.neighbor_asin, n.score
FROM staged_neighbors n
JOIN staged_products a ON a.asin = n.product_asin
JOIN staged_products b ON b.asin = n.neighbor_asin
"""


def load_catalog(
    connection: psycopg.Connection,
    products: Sequence[CatalogProduct],
    embeddings: dict[str, npt.NDArray[np.float16]],
    neighbors: Iterable[NeighborRow],
) -> LoadReport:
    missing = [product.asin for product in products if product.asin not in embeddings]
    if missing:
        raise ValueError(f"{len(missing)} products have no embedding; re-run the 'embed' step.")
    _require_schema(connection)

    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(_STAGE_PRODUCTS)
        with cursor.copy(f"COPY staged_products ({_PRODUCT_COLUMNS}) FROM STDIN") as copy:
            for product in products:
                copy.write_row(_product_row(product, embeddings[product.asin]))
        logger.info("Staged %d products", len(products))

        cursor.execute(_UPSERT_PRODUCTS)
        cursor.execute(_RETIRE_MISSING)
        retired = cursor.rowcount

        cursor.execute(_STAGE_NEIGHBORS)
        with cursor.copy(
            "COPY staged_neighbors (product_asin, rank, neighbor_asin, score) FROM STDIN"
        ) as copy:
            for row in neighbors:
                copy.write_row((row.product_asin, row.rank, row.neighbor_asin, row.score))
        cursor.execute("TRUNCATE product_neighbors")
        cursor.execute(_REPLACE_NEIGHBORS)
        neighbor_rows = cursor.rowcount

    # Outside the transaction: reclaim dead rows and refresh the planner's statistics.
    connection.execute("VACUUM (ANALYZE) products")
    connection.execute("VACUUM (ANALYZE) product_neighbors")
    size_row = connection.execute("SELECT pg_database_size(current_database())").fetchone()
    size_mb = (size_row[0] if size_row else 0) / 1e6
    return LoadReport(len(products), retired, neighbor_rows, round(size_mb, 1))


def _require_schema(connection: psycopg.Connection) -> None:
    row = connection.execute("SELECT to_regclass('product_neighbors') IS NOT NULL").fetchone()
    if not row or not row[0]:
        raise RuntimeError("The catalog tables don't exist yet; run 'alembic upgrade head' first.")


def _product_row(product: CatalogProduct, embedding: npt.NDArray[np.float16]) -> tuple[object, ...]:
    return (
        product.asin,
        product.title,
        product.brand,
        product.main_category,
        list(product.category_path),
        product.price,
        product.rating_average,
        product.rating_count,
        product.image_url,
        product.short_description,
        product.last_reviewed_on,
        _halfvec_literal(embedding),
    )


def _halfvec_literal(vector: npt.NDArray[np.float16]) -> str:
    return "[" + ",".join(f"{value:.5g}" for value in vector.astype(np.float32).tolist()) + "]"
