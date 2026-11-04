"""Product search, detail and also-liked, on a catalog loaded by the real pipeline."""

from collections.abc import Callable

import psycopg
import pytest
from httpx import AsyncClient

from pipelines.catalog import steps
from pipelines.catalog.config import SelectionRules
from pipelines.catalog.neighbors import AlsParameters
from pipelines.catalog.workspace import Workspace
from tests.api.conftest import Headers
from tests.catalog_samples import CATEGORY, COFFEE, YOGA, write_sample_dataset
from tests.fakes import HashingTextEmbedder

COFFEE_KIT = "B000COFFE1"
YOGA_MAT = "B000YOGAM1"


@pytest.fixture(scope="module")
def catalog(test_database_url: str, tmp_path_factory: pytest.TempPathFactory) -> Workspace:
    workspace = Workspace(tmp_path_factory.mktemp("catalog"))
    write_sample_dataset(workspace)
    steps.select(workspace, [CATEGORY], SelectionRules())
    steps.embed(workspace, HashingTextEmbedder())
    parameters = AlsParameters(factors=2, iterations=20, neighbors_per_product=4)
    steps.neighbors(workspace, [CATEGORY], parameters)
    steps.load(workspace, test_database_url)
    return workspace


@pytest.fixture
def user(catalog: Workspace, new_user: Callable[[], Headers]) -> Headers:
    return new_user()


async def search(
    client: AsyncClient, headers: Headers, **params: str | int
) -> list[dict[str, object]]:
    response = await client.get("/api/v1/products/search", params=params, headers=headers)
    assert response.status_code == 200, response.text
    items: list[dict[str, object]] = response.json()["items"]
    return items


async def test_search_finds_products_by_meaning(
    database_client: AsyncClient, user: Headers
) -> None:
    items = await search(database_client, user, q="coffee gift", limit=5)

    asins = [item["product"]["asin"] for item in items]  # type: ignore[index]
    assert len(asins) == 5
    assert set(asins) == set(COFFEE)
    scores = [item["score"] for item in items]
    assert scores == sorted(scores, reverse=True)  # type: ignore[type-var]


async def test_search_results_carry_amazon_links(
    database_client: AsyncClient, user: Headers
) -> None:
    [item] = await search(database_client, user, q="yoga mat", limit=1)
    product = item["product"]

    assert product == {
        "asin": YOGA_MAT,
        "title": "Non-Slip Yoga Mat",
        "brand": "Acme",
        "main_category": CATEGORY,
        "category_path": ["Home & Kitchen", "Kitchen & Dining"],
        "price_2023": "25.00",
        "rating_average": 4.6,
        "rating_count": 1200,
        "image_url": f"https://m.media-amazon.com/{YOGA_MAT}.jpg",
        "short_description": "A lovely non-slip yoga mat.",
        "amazon_url": f"https://www.amazon.com/dp/{YOGA_MAT}",
        "amazon_search_url": "https://www.amazon.com/s?k=Non-Slip+Yoga+Mat",
    }


async def test_search_respects_the_price_range(database_client: AsyncClient, user: Headers) -> None:
    # Sample prices run from $20 (first coffee product) up by a dollar each.
    items = await search(database_client, user, q="coffee", min_price=21, max_price=22, limit=10)

    prices = sorted(float(item["product"]["price_2023"]) for item in items)  # type: ignore[index]
    assert prices == [21.0, 22.0]


@pytest.mark.parametrize(
    "params",
    [
        {"q": "x"},
        {"q": "coffee", "limit": 51},
        {"q": "coffee", "min_price": 50, "max_price": 10},
        {"q": "coffee", "unknown": 1},
    ],
)
async def test_search_rejects_bad_parameters(
    database_client: AsyncClient, user: Headers, params: dict[str, str | int]
) -> None:
    response = await database_client.get("/api/v1/products/search", params=params, headers=user)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


async def test_product_detail(database_client: AsyncClient, user: Headers) -> None:
    response = await database_client.get(f"/api/v1/products/{COFFEE_KIT}", headers=user)

    assert response.status_code == 200
    assert response.json()["title"] == COFFEE[COFFEE_KIT]


@pytest.mark.parametrize(("asin", "status"), [("B0NOTFOUND", 404), ("not-an-asin", 422)])
async def test_unknown_or_malformed_products(
    database_client: AsyncClient, user: Headers, asin: str, status: int
) -> None:
    response = await database_client.get(f"/api/v1/products/{asin}", headers=user)

    assert response.status_code == status


async def test_also_liked_returns_products_liked_by_the_same_people(
    database_client: AsyncClient, user: Headers
) -> None:
    response = await database_client.get(
        f"/api/v1/products/{YOGA_MAT}/also-liked", params={"limit": 3}, headers=user
    )

    assert response.status_code == 200
    asins = [item["product"]["asin"] for item in response.json()["items"]]
    assert len(asins) == 3
    assert set(asins) <= set(YOGA) - {YOGA_MAT}


async def test_also_liked_for_an_unknown_product_is_not_found(
    database_client: AsyncClient, user: Headers
) -> None:
    response = await database_client.get("/api/v1/products/B0NOTFOUND/also-liked", headers=user)

    assert response.status_code == 404


async def test_products_need_sign_in(database_client: AsyncClient, catalog: Workspace) -> None:
    response = await database_client.get("/api/v1/products/search", params={"q": "coffee"})

    assert response.status_code == 401


def test_reloading_retires_products_dropped_from_the_catalog(
    catalog: Workspace, test_database_url: str
) -> None:
    products = catalog.products_file.read_text().splitlines()
    kept = [line for line in products if YOGA_MAT not in line]
    catalog.products_file.write_text("\n".join(kept) + "\n")
    try:
        report = steps.load(catalog, test_database_url)
        with psycopg.connect(test_database_url) as connection:
            row = connection.execute(
                "SELECT in_catalog FROM products WHERE asin = %s", (YOGA_MAT,)
            ).fetchone()
            linked = connection.execute(
                "SELECT count(*) FROM product_neighbors WHERE %s IN (product_asin, neighbor_asin)",
                (YOGA_MAT,),
            ).fetchone()
    finally:
        catalog.products_file.write_text("\n".join(products) + "\n")
        steps.load(catalog, test_database_url)

    assert report.products_loaded == 9
    assert report.products_retired == 1
    assert row == (False,)
    assert linked == (0,)
