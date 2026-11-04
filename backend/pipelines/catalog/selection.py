"""Turns raw dataset records into catalog products, keeping only good gifts."""

import logging
import re
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

from pipelines.catalog.config import SelectionRules
from pipelines.catalog.records import CatalogProduct

logger = logging.getLogger(__name__)

_ASIN = re.compile(r"^[A-Z0-9]{10}$")
_PRICE = re.compile(r"\d+(?:\.\d+)?")
_TITLE_MAX = 500
_BRAND_MAX = 200
_CATEGORY_MAX = 200
_CATEGORY_DEPTH_MAX = 8
_DESCRIPTION_MAX = 400
_FEATURE_MAX = 300


class Rejection(StrEnum):
    BAD_ASIN = "bad_asin"
    NO_TITLE = "no_title"
    NO_IMAGE = "no_image"
    NO_PRICE = "no_price"
    PRICE_OUT_OF_RANGE = "price_out_of_range"
    FEW_RATINGS = "few_ratings"
    LOW_RATING = "low_rating"
    EXCLUDED_CATEGORY = "excluded_category"
    NO_RECENT_REVIEWS = "no_recent_reviews"
    DUPLICATE = "duplicate"


@dataclass
class SelectionReport:
    category: str
    kept: int = 0
    rejected: Counter[Rejection] = field(default_factory=Counter)

    def summary(self) -> str:
        reasons = ", ".join(
            f"{reason.value}={count}" for reason, count in self.rejected.most_common()
        )
        return f"{self.category}: kept {self.kept}; rejected {reasons or 'none'}"


def last_review_dates(ratings: Iterable[tuple[str, date]]) -> dict[str, date]:
    """The newest review date per product."""
    latest: dict[str, date] = {}
    for asin, reviewed_on in ratings:
        if reviewed_on > latest.get(asin, date.min):
            latest[asin] = reviewed_on
    return latest


def to_catalog_product(
    record: Mapping[str, Any],
    category: str,
    last_reviewed: Mapping[str, date],
    rules: SelectionRules,
) -> CatalogProduct | Rejection:
    asin = str(record.get("parent_asin") or "")
    if not _ASIN.match(asin):
        return Rejection.BAD_ASIN
    title = _clean(record.get("title"), _TITLE_MAX)
    if not title:
        return Rejection.NO_TITLE
    image_url = _main_image(record.get("images"))
    if image_url is None:
        return Rejection.NO_IMAGE
    price = _price(record.get("price"))
    if price is None:
        return Rejection.NO_PRICE
    if not rules.min_price <= price <= rules.max_price:
        return Rejection.PRICE_OUT_OF_RANGE
    rating_count = _int(record.get("rating_number"))
    if rating_count < rules.min_rating_count:
        return Rejection.FEW_RATINGS
    rating_average = _float(record.get("average_rating"))
    if not rules.min_rating_average <= rating_average <= 5:
        return Rejection.LOW_RATING
    category_path = _category_path(record.get("categories"))
    if _is_excluded(category_path, rules.excluded_category_terms):
        return Rejection.EXCLUDED_CATEGORY
    last_reviewed_on = last_reviewed.get(asin)
    if last_reviewed_on is None or last_reviewed_on < rules.reviewed_since:
        return Rejection.NO_RECENT_REVIEWS

    features = tuple(
        cleaned
        for item in _strings(record.get("features"))
        if (cleaned := _clean(item, _FEATURE_MAX))
    )
    descriptions = [_clean(item, _DESCRIPTION_MAX) for item in _strings(record.get("description"))]
    short_description = next((text for text in [*descriptions, *features] if text), None)
    return CatalogProduct(
        asin=asin,
        title=title,
        brand=_brand(record),
        main_category=category,
        category_path=category_path,
        price=price,
        rating_average=round(rating_average, 1),
        rating_count=rating_count,
        image_url=image_url,
        short_description=short_description,
        features=features,
        last_reviewed_on=last_reviewed_on,
    )


def select_top(
    records: Iterable[Mapping[str, Any]],
    category: str,
    last_reviewed: Mapping[str, date],
    rules: SelectionRules,
    quota: int,
    already_selected: set[str],
) -> tuple[list[CatalogProduct], SelectionReport]:
    """The ``quota`` most-reviewed products of a category that pass every rule."""
    report = SelectionReport(category)
    candidates: list[CatalogProduct] = []
    for record in records:
        outcome = to_catalog_product(record, category, last_reviewed, rules)
        if isinstance(outcome, Rejection):
            report.rejected[outcome] += 1
        elif outcome.asin in already_selected:
            report.rejected[Rejection.DUPLICATE] += 1
        else:
            candidates.append(outcome)

    candidates.sort(
        key=lambda product: (product.rating_count, product.rating_average), reverse=True
    )
    selected: list[CatalogProduct] = []
    for product in candidates:
        if len(selected) == quota:
            break
        if product.asin in already_selected:
            report.rejected[Rejection.DUPLICATE] += 1
            continue
        already_selected.add(product.asin)
        selected.append(product)
    report.kept = len(selected)
    return selected, report


def _clean(value: object, max_length: int) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:max_length]


def _strings(value: object) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _price(value: object) -> Decimal | None:
    # Prices appear as numbers, as strings like "29.99" or "$29.99", or as junk ("—").
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        text = str(value)
    elif isinstance(value, str) and (match := _PRICE.search(value.replace(",", ""))):
        text = match.group()
    else:
        return None
    try:
        price = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return price if price > 0 else None


def _int(value: object) -> int:
    if isinstance(value, int | float | str) and not isinstance(value, bool):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _float(value: object) -> float:
    if isinstance(value, int | float | str) and not isinstance(value, bool):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


def _main_image(images: object) -> str | None:
    if not isinstance(images, list):
        return None
    entries = [image for image in images if isinstance(image, dict)]
    entries.sort(key=lambda image: image.get("variant") != "MAIN")
    for image in entries:
        for size in ("large", "hi_res", "thumb"):
            url = image.get(size)
            if isinstance(url, str) and url.startswith("https://") and len(url) <= 1000:
                return url
    return None


def _brand(record: Mapping[str, Any]) -> str | None:
    details = record.get("details")
    detail_brand = details.get("Brand") if isinstance(details, dict) else None
    brand = _clean(record.get("store") or detail_brand, _BRAND_MAX)
    return brand or None


def _category_path(categories: object) -> tuple[str, ...]:
    path = (_clean(item, _CATEGORY_MAX) for item in _strings(categories))
    return tuple(item for item in path if item)[:_CATEGORY_DEPTH_MAX]


def _is_excluded(category_path: tuple[str, ...], excluded_terms: frozenset[str]) -> bool:
    return any(term in level.lower() for level in category_path for term in excluded_terms)
