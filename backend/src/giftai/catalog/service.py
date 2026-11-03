from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from giftai.catalog.models import Product
from giftai.catalog.repository import ProductRepository
from giftai.catalog.schemas import NeighborsQuery, ProductSearchQuery
from giftai.core.errors import NotFoundError
from giftai.embeddings.base import TextEmbedder


class ProductCatalogService:
    def __init__(self, session: AsyncSession, embedder: TextEmbedder) -> None:
        self._products = ProductRepository(session)
        self._embedder = embedder

    async def search(self, query: ProductSearchQuery) -> list[tuple[Product, float]]:
        # Embedding is CPU work; a worker thread keeps the event loop serving others.
        embedding = await run_in_threadpool(self._embedder.embed_query, query.q)
        return await self._products.search_by_embedding(
            embedding.tolist(),
            query.limit,
            min_price=_dollars(query.min_price),
            max_price=_dollars(query.max_price),
        )

    async def get(self, asin: str) -> Product:
        product = await self._products.get(asin)
        if product is None:
            raise NotFoundError("We couldn't find that product.")
        return product

    async def also_liked(self, asin: str, query: NeighborsQuery) -> list[tuple[Product, float]]:
        await self.get(asin)  # a clear 404 rather than an empty list for a wrong id
        return await self._products.neighbors(asin, query.limit)


def _dollars(amount: int | None) -> Decimal | None:
    return None if amount is None else Decimal(amount)
