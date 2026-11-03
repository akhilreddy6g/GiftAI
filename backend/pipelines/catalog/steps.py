"""The pipeline's steps, each reading and writing files in the workspace."""

import json
import logging
from collections.abc import Iterator, Sequence
from pathlib import Path

import numpy as np
import psycopg

from giftai.core.config import get_database_settings
from giftai.embeddings.base import TextEmbedder
from pipelines.catalog import dataset
from pipelines.catalog.config import SelectionRules, quota_for
from pipelines.catalog.embedding import ProductEmbeddings, embed_products
from pipelines.catalog.loading import LoadReport, NeighborRow, load_catalog
from pipelines.catalog.neighbors import (
    AlsParameters,
    build_interactions,
    evaluate,
    nearest_neighbors,
    report_dict,
    train,
)
from pipelines.catalog.records import read_products, write_products
from pipelines.catalog.selection import last_review_dates, select_top
from pipelines.catalog.workspace import Workspace

logger = logging.getLogger(__name__)


def download(workspace: Workspace, categories: Sequence[str]) -> None:
    for category in categories:
        dataset.download(dataset.meta_url(category), workspace.meta_file(category))
        dataset.download(dataset.ratings_url(category), workspace.ratings_file(category))


def select(
    workspace: Workspace, categories: Sequence[str], rules: SelectionRules, scale: float = 1.0
) -> int:
    selected_asins: set[str] = set()
    total = 0
    write_products(workspace.products_file, [])  # start empty; categories append below
    for category in categories:
        ratings_path = workspace.require(workspace.ratings_file(category), "download")
        meta_path = workspace.require(workspace.meta_file(category), "download")
        logger.info("Reading %s review dates", category)
        last_reviewed = last_review_dates(
            (rating.asin, rating.reviewed_on) for rating in dataset.iter_ratings(ratings_path)
        )
        logger.info("Selecting %s products", category)
        products, report = select_top(
            dataset.iter_metadata(meta_path),
            category,
            last_reviewed,
            rules,
            quota_for(category, scale),
            selected_asins,
        )
        logger.info(report.summary())
        total += write_products(workspace.products_file, products, append=True)
    logger.info("Selected %d products in total", total)
    return total


def embed(workspace: Workspace, embedder: TextEmbedder) -> None:
    products = list(read_products(workspace.require(workspace.products_file, "select")))
    result = embed_products(products, embedder)
    np.savez(workspace.embeddings_file, asins=result.asins, vectors=result.vectors)
    logger.info("Saved %d embeddings", len(result.asins))


def neighbors(
    workspace: Workspace, categories: Sequence[str], parameters: AlsParameters
) -> dict[str, object]:
    products = list(read_products(workspace.require(workspace.products_file, "select")))
    asins = [product.asin for product in products]
    item_index = {asin: index for index, asin in enumerate(asins)}

    def all_ratings() -> Iterator[dataset.Rating]:
        for category in categories:
            yield from dataset.iter_ratings(
                workspace.require(workspace.ratings_file(category), "download")
            )

    interactions = build_interactions(all_ratings(), item_index, parameters)
    logger.info(
        "Training on %d likes from %d reviewers", len(interactions.users), interactions.user_count
    )
    evaluation = evaluate(interactions, parameters)
    logger.info(
        "Recall@10: ALS %.3f vs popularity %.3f; Recall@50: ALS %.3f vs popularity %.3f",
        evaluation.als_recall_at_10,
        evaluation.popularity_recall_at_10,
        evaluation.als_recall_at_50,
        evaluation.popularity_recall_at_50,
    )

    model = train(interactions.matrix(), parameters)
    item_likes = np.bincount(interactions.items, minlength=interactions.item_count)
    result = nearest_neighbors(model, item_likes, parameters)
    asin_array = np.array(asins, dtype="<U10")
    np.savez(
        workspace.neighbors_file,
        product_asins=asin_array[result.products],
        ranks=result.ranks,
        neighbor_asins=asin_array[result.neighbors],
        scores=result.scores,
    )
    report = report_dict(evaluation, parameters, interactions)
    report["products_with_neighbors"] = len(np.unique(result.products))
    workspace.neighbors_report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info(
        "Saved %d neighbor rows; report in %s", len(result.ranks), workspace.neighbors_report_file
    )
    return report


def load(workspace: Workspace, database_url: str | None = None) -> LoadReport:
    products = list(read_products(workspace.require(workspace.products_file, "select")))
    embeddings = _read_embeddings(workspace.require(workspace.embeddings_file, "embed"))
    neighbor_rows = _read_neighbors(workspace.require(workspace.neighbors_file, "neighbors"))
    url = database_url or _libpq_url(get_database_settings().sqlalchemy_database_url)
    with psycopg.connect(url, autocommit=True) as connection:
        report = load_catalog(connection, products, embeddings.by_asin(), neighbor_rows)
    logger.info(
        "Loaded %d products (%d retired) and %d neighbor rows; database is now %.1f MB",
        report.products_loaded,
        report.products_retired,
        report.neighbor_rows,
        report.database_size_mb,
    )
    return report


def _read_embeddings(path: Path) -> ProductEmbeddings:
    with np.load(path, allow_pickle=False) as data:
        return ProductEmbeddings(data["asins"], data["vectors"])


def _read_neighbors(path: Path) -> list[NeighborRow]:
    with np.load(path, allow_pickle=False) as data:
        return [
            NeighborRow(str(product), int(rank), str(neighbor), float(score))
            for product, rank, neighbor, score in zip(
                data["product_asins"],
                data["ranks"],
                data["neighbor_asins"],
                data["scores"],
                strict=True,
            )
        ]


def _libpq_url(sqlalchemy_url: str) -> str:
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)
