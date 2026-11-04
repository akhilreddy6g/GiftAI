from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from pipelines.catalog.config import SelectionRules
from pipelines.catalog.records import CatalogProduct
from pipelines.catalog.selection import Rejection, select_top, to_catalog_product

RULES = SelectionRules()
RECENT = {"B0TESTASIN": date(2023, 6, 1)}


def record(**overrides: Any) -> dict[str, Any]:
    return {
        "parent_asin": "B0TESTASIN",
        "title": "  Hario   V60 Pour-Over Kit ",
        "average_rating": 4.7,
        "rating_number": 18402,
        "price": 29.99,
        "images": [{"large": "https://m.media-amazon.com/main.jpg", "variant": "MAIN"}],
        "store": "Hario",
        "categories": ["Home & Kitchen", "Coffee"],
        "features": ["Includes dripper and filters"],
        "description": [],
    } | overrides


def test_a_good_gift_becomes_a_catalog_product() -> None:
    product = to_catalog_product(record(), "Home_and_Kitchen", RECENT, RULES)

    assert isinstance(product, CatalogProduct)
    assert product.title == "Hario V60 Pour-Over Kit"
    assert product.price == Decimal("29.99")
    assert product.brand == "Hario"
    assert product.category_path == ("Home & Kitchen", "Coffee")
    assert product.short_description == "Includes dripper and filters"
    assert product.last_reviewed_on == date(2023, 6, 1)


@pytest.mark.parametrize(
    ("raw_price", "expected"),
    [(29.99, Decimal("29.99")), ("$1,049.00", None), ("12.5", Decimal("12.50")), ("—", None)],
)
def test_prices_are_parsed_from_numbers_and_strings(
    raw_price: object, expected: Decimal | None
) -> None:
    outcome = to_catalog_product(record(price=raw_price), "Home_and_Kitchen", RECENT, RULES)

    if expected is None:
        # "$1,049.00" parses but is over the gift price range; "—" has no price at all.
        assert isinstance(outcome, Rejection)
    else:
        assert isinstance(outcome, CatalogProduct)
        assert outcome.price == expected


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"parent_asin": "short"}, Rejection.BAD_ASIN),
        ({"title": "   "}, Rejection.NO_TITLE),
        ({"images": [{"large": "http://insecure.example/x.jpg"}]}, Rejection.NO_IMAGE),
        ({"price": None}, Rejection.NO_PRICE),
        ({"price": 2.5}, Rejection.PRICE_OUT_OF_RANGE),
        ({"rating_number": 10}, Rejection.FEW_RATINGS),
        ({"average_rating": "3.1"}, Rejection.LOW_RATING),
        ({"categories": ["Electronics", "Batteries"]}, Rejection.EXCLUDED_CATEGORY),
    ],
)
def test_each_rule_rejects_with_its_reason(overrides: dict[str, Any], reason: Rejection) -> None:
    assert to_catalog_product(record(**overrides), "Home_and_Kitchen", RECENT, RULES) is reason


def test_products_without_recent_reviews_are_rejected() -> None:
    old = {"B0TESTASIN": date(2021, 1, 1)}

    assert (
        to_catalog_product(record(), "Home_and_Kitchen", old, RULES) is Rejection.NO_RECENT_REVIEWS
    )
    assert (
        to_catalog_product(record(), "Home_and_Kitchen", {}, RULES) is Rejection.NO_RECENT_REVIEWS
    )


def test_selection_keeps_the_most_reviewed_and_skips_products_already_chosen() -> None:
    asins = [f"B0TEST{index:04d}" for index in range(4)]
    records = [
        record(parent_asin=asin, rating_number=100 * (index + 1))
        for index, asin in enumerate(asins)
    ]
    recent = dict.fromkeys(asins, date(2023, 6, 1))
    already_selected = {asins[3]}

    selected, report = select_top(records, "Toys_and_Games", recent, RULES, 2, already_selected)

    assert [product.asin for product in selected] == [asins[2], asins[1]]
    assert report.kept == 2
    assert report.rejected[Rejection.DUPLICATE] == 1
    assert already_selected == {asins[1], asins[2], asins[3]}
