"""The select, embed and neighbors steps on a miniature dataset (no database needed)."""

import json
from pathlib import Path

import numpy as np
import pytest

from pipelines.catalog import steps
from pipelines.catalog.config import SelectionRules
from pipelines.catalog.neighbors import AlsParameters
from pipelines.catalog.records import read_products
from pipelines.catalog.workspace import Workspace
from tests.catalog_samples import CATEGORY, COFFEE, YOGA, write_sample_dataset
from tests.fakes import HashingTextEmbedder

# Two factors for two tastes; more would let ALS memorise ten products one by one.
SMALL_ALS = AlsParameters(factors=2, iterations=20, min_item_likes=5, neighbors_per_product=4)


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> Workspace:
    workspace = Workspace(tmp_path_factory.mktemp("catalog"))
    write_sample_dataset(workspace)
    steps.select(workspace, [CATEGORY], SelectionRules())
    steps.embed(workspace, HashingTextEmbedder())
    steps.neighbors(workspace, [CATEGORY], SMALL_ALS)
    return workspace


def test_select_keeps_only_products_that_pass_every_rule(workspace: Workspace) -> None:
    selected = {product.asin for product in read_products(workspace.products_file)}

    assert selected == set(COFFEE) | set(YOGA)


def test_embed_writes_one_unit_vector_per_product(workspace: Workspace) -> None:
    with np.load(workspace.embeddings_file, allow_pickle=False) as data:
        asins, vectors = data["asins"], data["vectors"]

    assert set(asins.tolist()) == set(COFFEE) | set(YOGA)
    assert vectors.shape == (10, 384)
    assert vectors.dtype == np.float16
    np.testing.assert_allclose(np.linalg.norm(vectors.astype(np.float32), axis=1), 1.0, atol=1e-2)


def test_neighbors_stay_within_a_taste(workspace: Workspace) -> None:
    with np.load(workspace.neighbors_file, allow_pickle=False) as data:
        pairs = list(
            zip(data["product_asins"].tolist(), data["neighbor_asins"].tolist(), strict=True)
        )
        ranks = data["ranks"]

    assert pairs
    assert set(ranks.tolist()) <= {1, 2, 3, 4}
    for product, neighbor in pairs:
        assert product != neighbor
        same_taste = {product, neighbor} <= set(COFFEE) or {product, neighbor} <= set(YOGA)
        assert same_taste, f"{product} and {neighbor} were liked by different people"


def test_neighbors_report_records_the_evaluation(workspace: Workspace) -> None:
    report = json.loads(Path(workspace.neighbors_report_file).read_text())

    assert report["users"] == 60
    assert report["likes"] == 240
    assert report["evaluation"]["users_evaluated"] == 60
    assert report["parameters"]["factors"] == 2
    assert report["products_with_neighbors"] == 10
