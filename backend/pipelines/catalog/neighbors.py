"""Collaborative filtering: which products the same people liked, learned with ALS.

ALS (alternating least squares) factorises the reviewer-by-product matrix into a short
vector per reviewer and per product, so that products liked by similar reviewers end up
with similar vectors. Each product's closest vectors become its "also liked" list.

Quality is measured before anything ships: for reviewers with three or more liked
products, the newest one is hidden, the model trains on the rest, and Recall@K counts how
often the hidden product is in the model's top K. A popularity baseline (everyone gets
the most-liked products) shows whether ALS actually learned something.
"""

import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass

import numpy as np
import numpy.typing as npt
from implicit.als import AlternatingLeastSquares
from scipy.sparse import csr_matrix
from threadpoolctl import threadpool_limits

from pipelines.catalog.dataset import Rating

logger = logging.getLogger(__name__)

IntArray = npt.NDArray[np.int64]
FloatArray = npt.NDArray[np.float32]

_SCORING_BATCH = 256


@dataclass(frozen=True)
class AlsParameters:
    factors: int = 64
    regularization: float = 0.05
    # How much more an observed "like" counts than an unobserved pair.
    alpha: float = 20.0
    iterations: int = 15
    # Only ratings at or above this count as liking a product.
    min_liked_rating: float = 4.0
    # Products liked by fewer people get no list and appear in no list: too little signal.
    min_item_likes: int = 5
    # 20 is plenty to widen a search; 50 would push the catalog past the free 1 GB.
    neighbors_per_product: int = 20
    evaluation_users: int = 10_000
    random_seed: int = 42


@dataclass(frozen=True)
class Interactions:
    """Who liked what, as parallel arrays of user index, item index and time."""

    users: IntArray
    items: IntArray
    timestamps: IntArray
    user_count: int
    item_count: int

    def matrix(self, mask: npt.NDArray[np.bool_] | None = None) -> csr_matrix:
        users = self.users if mask is None else self.users[mask]
        items = self.items if mask is None else self.items[mask]
        values = np.ones(len(users), dtype=np.float32)
        matrix = csr_matrix((values, (users, items)), shape=(self.user_count, self.item_count))
        matrix.sum_duplicates()
        matrix.data[:] = 1.0  # a repeat review is still one "like"
        return matrix


@dataclass(frozen=True)
class EvaluationReport:
    users_evaluated: int
    als_recall_at_10: float
    als_recall_at_50: float
    popularity_recall_at_10: float
    popularity_recall_at_50: float


@dataclass(frozen=True)
class Neighbors:
    """Flat rows: product index, rank (1 = closest), neighbor index, similarity."""

    products: IntArray
    ranks: IntArray
    neighbors: IntArray
    scores: FloatArray


def build_interactions(
    ratings: Iterable[Rating], item_index: dict[str, int], parameters: AlsParameters
) -> Interactions:
    """Likes of catalog products, from users with at least two of them (one like links
    nothing to anything else).
    """
    user_index: dict[str, int] = {}
    users: list[int] = []
    items: list[int] = []
    timestamps: list[int] = []
    for rating in ratings:
        item = item_index.get(rating.asin)
        if item is None or rating.rating < parameters.min_liked_rating:
            continue
        users.append(user_index.setdefault(rating.user_id, len(user_index)))
        items.append(item)
        timestamps.append(int(rating.reviewed_at.timestamp()))

    user_array = np.asarray(users, dtype=np.int64)
    likes_per_user = np.bincount(user_array, minlength=len(user_index))
    keep = likes_per_user[user_array] >= 2
    # Re-number the surviving users densely so the matrix has no empty rows.
    kept_users, dense_users = np.unique(user_array[keep], return_inverse=True)
    return Interactions(
        users=dense_users.astype(np.int64),
        items=np.asarray(items, dtype=np.int64)[keep],
        timestamps=np.asarray(timestamps, dtype=np.int64)[keep],
        user_count=len(kept_users),
        item_count=len(item_index),
    )


def train(matrix: csr_matrix, parameters: AlsParameters) -> AlternatingLeastSquares:
    # implicit runs its own threads; nested BLAS threads would only fight over the cores.
    with threadpool_limits(limits=1, user_api="blas"):
        model = AlternatingLeastSquares(
            factors=parameters.factors,
            regularization=parameters.regularization,
            alpha=parameters.alpha,
            iterations=parameters.iterations,
            random_state=parameters.random_seed,
            use_gpu=False,
        )
        model.fit(matrix, show_progress=False)
    return model


def evaluate(interactions: Interactions, parameters: AlsParameters) -> EvaluationReport:
    """Leave-newest-out Recall@10 and @50 for ALS and for a popularity baseline."""
    holdout = _newest_like_of_each_eligible_user(interactions)
    rng = np.random.default_rng(parameters.random_seed)
    eval_rows = np.flatnonzero(holdout >= 0)
    if len(eval_rows) > parameters.evaluation_users:
        eval_rows = rng.choice(eval_rows, size=parameters.evaluation_users, replace=False)
    if len(eval_rows) == 0:
        return EvaluationReport(0, 0.0, 0.0, 0.0, 0.0)

    train_mask = np.ones(len(interactions.users), dtype=bool)
    train_mask[holdout[holdout >= 0]] = False
    train_matrix = interactions.matrix(train_mask)
    model = train(train_matrix, parameters)

    held_out_items = interactions.items[holdout[eval_rows]]
    user_factors = np.asarray(model.user_factors, dtype=np.float32)
    item_factors = np.asarray(model.item_factors, dtype=np.float32)
    popularity = np.asarray(train_matrix.sum(axis=0), dtype=np.float32).ravel()

    als_hits = {10: 0, 50: 0}
    popular_hits = {10: 0, 50: 0}
    for start in range(0, len(eval_rows), _SCORING_BATCH):
        users = eval_rows[start : start + _SCORING_BATCH]
        liked = train_matrix[users].toarray() > 0
        targets = held_out_items[start : start + _SCORING_BATCH]
        als_scores = np.where(liked, -np.inf, user_factors[users] @ item_factors.T)
        popular_scores = np.where(liked, -np.inf, np.broadcast_to(popularity, liked.shape))
        for k in (10, 50):
            als_hits[k] += _hits_in_top_k(als_scores, targets, k)
            popular_hits[k] += _hits_in_top_k(popular_scores, targets, k)

    count = len(eval_rows)
    return EvaluationReport(
        users_evaluated=count,
        als_recall_at_10=als_hits[10] / count,
        als_recall_at_50=als_hits[50] / count,
        popularity_recall_at_10=popular_hits[10] / count,
        popularity_recall_at_50=popular_hits[50] / count,
    )


def nearest_neighbors(
    model: AlternatingLeastSquares, item_likes: IntArray, parameters: AlsParameters
) -> Neighbors:
    """Each eligible product's closest eligible products by cosine of ALS factors."""
    factors = np.asarray(model.item_factors, dtype=np.float32)
    norms = np.linalg.norm(factors, axis=1, keepdims=True)
    unit = np.divide(factors, norms, out=np.zeros_like(factors), where=norms > 0)
    eligible = np.flatnonzero(item_likes >= parameters.min_item_likes)
    k = min(parameters.neighbors_per_product, len(eligible) - 1)
    if k <= 0:
        empty = np.empty(0, dtype=np.int64)
        return Neighbors(empty, empty, empty, np.empty(0, dtype=np.float32))

    candidate_vectors = unit[eligible]
    products: list[IntArray] = []
    ranks: list[IntArray] = []
    neighbors: list[IntArray] = []
    scores: list[FloatArray] = []
    for start in range(0, len(eligible), _SCORING_BATCH):
        sources = eligible[start : start + _SCORING_BATCH]
        similarity = unit[sources] @ candidate_vectors.T
        # A product is not its own neighbor.
        similarity[np.arange(len(sources)), np.arange(start, start + len(sources))] = -np.inf
        top = np.argpartition(-similarity, k - 1, axis=1)[:, :k]
        top_scores = np.take_along_axis(similarity, top, axis=1)
        order = np.argsort(-top_scores, axis=1)
        top = np.take_along_axis(top, order, axis=1)
        top_scores = np.take_along_axis(top_scores, order, axis=1)
        positive = top_scores > 0
        products.append(np.repeat(sources, k).reshape(-1, k)[positive])
        ranks.append(np.tile(np.arange(1, k + 1), (len(sources), 1))[positive])
        neighbors.append(eligible[top][positive])
        scores.append(top_scores[positive].astype(np.float32))
    return Neighbors(
        products=np.concatenate(products),
        ranks=np.concatenate(ranks),
        neighbors=np.concatenate(neighbors),
        scores=np.concatenate(scores),
    )


def report_dict(
    report: EvaluationReport, parameters: AlsParameters, interactions: Interactions
) -> dict[str, object]:
    return {
        "parameters": asdict(parameters),
        "users": interactions.user_count,
        "likes": len(interactions.users),
        "evaluation": asdict(report),
    }


def _newest_like_of_each_eligible_user(interactions: Interactions) -> IntArray:
    """For each user with at least three likes, the row index of their newest like; -1
    for everyone else (they keep all their likes for training).
    """
    order = np.lexsort((interactions.timestamps, interactions.users))
    sorted_users = interactions.users[order]
    is_last = np.ones(len(order), dtype=bool)
    is_last[:-1] = sorted_users[:-1] != sorted_users[1:]
    likes = np.bincount(interactions.users, minlength=interactions.user_count)
    holdout = np.full(interactions.user_count, -1, dtype=np.int64)
    last_rows = order[is_last]
    last_users = interactions.users[last_rows]
    eligible = likes[last_users] >= 3
    holdout[last_users[eligible]] = last_rows[eligible]
    return holdout


def _hits_in_top_k(scores: FloatArray, targets: IntArray, k: int) -> int:
    k = min(k, scores.shape[1])
    top = np.argpartition(-scores, k - 1, axis=1)[:, :k]
    return int((top == targets[:, None]).any(axis=1).sum())
