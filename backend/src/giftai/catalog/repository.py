from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.catalog.models import Product, ProductNeighbor

# How many graph candidates HNSW keeps while searching. It must be at least the number of
# results wanted, or the index silently returns fewer (pgvector's default is 40).
_MIN_EF_SEARCH = 100


class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, asin: str) -> Product | None:
        return await self._session.get(Product, asin)

    async def search_by_embedding(
        self,
        embedding: Sequence[float],
        limit: int,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
    ) -> list[tuple[Product, float]]:
        """In-catalog products closest in meaning, as (product, cosine similarity)."""
        await self._tune_index_scan(limit)
        distance = Product.embedding.cosine_distance(embedding)
        conditions: list[ColumnElement[bool]] = [Product.in_catalog.is_(True)]
        if min_price is not None:
            conditions.append(Product.price_2023 >= min_price)
        if max_price is not None:
            conditions.append(Product.price_2023 <= max_price)

        rows = await self._session.execute(
            select(Product, distance.label("distance"))
            .where(*conditions)
            .order_by(distance)
            .limit(limit)
        )
        # Relaxed-order scans can return near-ties slightly out of order; settle them here.
        results = [(product, 1.0 - float(row_distance)) for product, row_distance in rows]
        return sorted(results, key=lambda result: result[1], reverse=True)

    async def neighbors(self, asin: str, limit: int) -> list[tuple[Product, float]]:
        """In-catalog products liked by the same people, closest first."""
        rows = await self._session.execute(
            select(Product, ProductNeighbor.score)
            .join(ProductNeighbor, ProductNeighbor.neighbor_asin == Product.asin)
            .where(ProductNeighbor.product_asin == asin, Product.in_catalog)
            .order_by(ProductNeighbor.rank)
            .limit(limit)
        )
        return [(product, float(score)) for product, score in rows]

    async def _tune_index_scan(self, limit: int) -> None:
        # Both settings last only for this transaction. Iterative scans (pgvector 0.8+)
        # keep searching when filters such as the price range discard index hits.
        await self._session.execute(
            select(
                func.set_config("hnsw.ef_search", str(max(_MIN_EF_SEARCH, limit)), True),
                func.set_config("hnsw.iterative_scan", "relaxed_order", True),
            )
        )
