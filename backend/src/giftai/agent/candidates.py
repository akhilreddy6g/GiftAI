"""Gathers candidate products from two sources: meaning search for each of the agent's
queries, and the "also liked" neighbors of the best search hits.
"""

from decimal import Decimal

from starlette.concurrency import run_in_threadpool

from giftai.agent.ranking import Candidate
from giftai.catalog.repository import ProductRepository
from giftai.embeddings.base import TextEmbedder

RESULTS_PER_QUERY = 60
SEEDS_FOR_NEIGHBORS = 8
NEIGHBORS_PER_SEED = 10
# Neighbors earn relevance through the search hit they came from, a little discounted.
NEIGHBOR_DISCOUNT = 0.9
# 2023 prices drift, so the search looks a little beyond the budget; ranking then
# prefers products inside it.
PRICE_SLACK = Decimal("0.25")


async def gather_candidates(
    products: ProductRepository,
    embedder: TextEmbedder,
    queries: list[str],
    budget: tuple[int | None, int | None],
) -> list[Candidate]:
    low, high = budget
    min_price = None if low is None else Decimal(low) * (1 - PRICE_SLACK)
    max_price = None if high is None else Decimal(high) * (1 + PRICE_SLACK)

    by_asin: dict[str, Candidate] = {}
    # Embedding is CPU work; one batch in a worker thread keeps the event loop free.
    vectors = await run_in_threadpool(lambda: [embedder.embed_query(q) for q in queries])
    for query, vector in zip(queries, vectors, strict=True):
        hits = await products.search_by_embedding(
            vector.tolist(), RESULTS_PER_QUERY, min_price=min_price, max_price=max_price
        )
        for product, similarity in hits:
            candidate = by_asin.get(product.asin)
            if candidate is None:
                by_asin[product.asin] = Candidate(product, similarity, {f"search:{query}"})
            else:
                candidate.relevance = max(candidate.relevance, similarity)
                candidate.found_by.add(f"search:{query}")

    seeds = sorted(by_asin.values(), key=lambda c: -c.relevance)[:SEEDS_FOR_NEIGHBORS]
    for seed in seeds:
        for product, neighbor_score in await products.neighbors(
            seed.product.asin, NEIGHBORS_PER_SEED
        ):
            if not _within(product.price_2023, min_price, max_price):
                continue
            relevance = seed.relevance * NEIGHBOR_DISCOUNT * (0.7 + 0.3 * neighbor_score)
            candidate = by_asin.get(product.asin)
            if candidate is None:
                by_asin[product.asin] = Candidate(product, relevance, {"also_liked"})
            else:
                candidate.relevance = max(candidate.relevance, relevance)
                candidate.found_by.add("also_liked")
    return list(by_asin.values())


def _within(price: Decimal, low: Decimal | None, high: Decimal | None) -> bool:
    return (low is None or price >= low) and (high is None or price <= high)
