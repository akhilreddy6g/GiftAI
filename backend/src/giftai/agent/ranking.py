"""Turns about 200 candidate products into the 20 best, with a hand-set linear score.

Iteration 1 of the design: the weights are set by hand; a learned ranker (LightGBM)
replaces ``score`` later, fed by the same features.
"""

import math
from dataclasses import dataclass, field
from decimal import Decimal

from giftai.catalog.models import Product

# How much each feature counts. Meaning comes first (a perfect-fit price on the wrong
# kind of product is still the wrong gift), then staying near the budget.
WEIGHTS = {
    "relevance": 0.50,
    "price_fit": 0.25,
    "rating": 0.12,
    "popularity": 0.08,
    "freshness": 0.05,
}
# Shown in an earlier answer in this chat: still allowed, but new ideas come first.
ALREADY_SHOWN_PENALTY = 0.15
# Keeps the shortlist varied: at most this many from one leaf category.
MAX_PER_CATEGORY = 3


@dataclass
class Candidate:
    product: Product
    # Cosine similarity to the best-matching search, or derived from a neighbor's.
    relevance: float
    found_by: set[str] = field(default_factory=set)
    score: float = 0.0
    features: dict[str, float] = field(default_factory=dict)


def price_fit(price: Decimal, low: int | None, high: int | None) -> float:
    """1 inside the budget, falling off smoothly outside it (2023 prices drift)."""
    value = float(price)
    if high is not None and value > high:
        return math.exp(-3 * (value - high) / max(high, 1))
    if low is not None and value < low:
        return math.exp(-3 * (low - value) / max(low, 1))
    return 1.0


def features(candidate: Candidate, low: int | None, high: int | None) -> dict[str, float]:
    product = candidate.product
    return {
        "relevance": max(0.0, min(1.0, candidate.relevance)),
        "price_fit": price_fit(product.price_2023, low, high),
        # 3 stars and below scores 0; 5 stars scores 1.
        "rating": max(0.0, min(1.0, (product.rating_average - 3.0) / 2.0)),
        # 10 ratings is about 0.25, 10,000 is 1.
        "popularity": max(0.0, min(1.0, math.log10(max(product.rating_count, 1)) / 4.0)),
        "freshness": 1.0 if product.last_reviewed_on is not None else 0.0,
    }


def rank(
    candidates: list[Candidate],
    budget: tuple[int | None, int | None],
    already_shown: set[str],
    limit: int = 20,
) -> list[Candidate]:
    low, high = budget
    for candidate in candidates:
        candidate.features = features(candidate, low, high)
        candidate.score = sum(WEIGHTS[name] * value for name, value in candidate.features.items())
        if candidate.product.asin in already_shown:
            candidate.score -= ALREADY_SHOWN_PENALTY

    ranked = sorted(candidates, key=lambda c: (-c.score, c.product.asin))
    shortlist: list[Candidate] = []
    held_back: list[Candidate] = []
    per_category: dict[str, int] = {}
    for candidate in ranked:
        category = _leaf_category(candidate.product)
        if per_category.get(category, 0) >= MAX_PER_CATEGORY:
            held_back.append(candidate)
            continue
        per_category[category] = per_category.get(category, 0) + 1
        shortlist.append(candidate)
        if len(shortlist) == limit:
            return shortlist
    # Few categories matched: variety gives way rather than leaving the list short.
    return shortlist + held_back[: limit - len(shortlist)]


def _leaf_category(product: Product) -> str:
    return product.category_path[-1] if product.category_path else product.main_category
