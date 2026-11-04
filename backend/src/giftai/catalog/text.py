"""The text that represents a product for meaning search.

The offline pipeline embeds exactly this text for every product, so the format lives here
in one place. Changing it means re-embedding the catalog.
"""

from collections.abc import Sequence

_MAX_FEATURES = 5
_MAX_LENGTH = 1200


def product_document(
    title: str, brand: str | None, category_path: Sequence[str], features: Sequence[str]
) -> str:
    parts = [title.strip()]
    if brand:
        parts.append(f"Brand: {brand.strip()}")
    if category_path:
        parts.append(f"Category: {' > '.join(category_path)}")
    parts.extend(feature.strip() for feature in features[:_MAX_FEATURES] if feature.strip())
    return ". ".join(parts)[:_MAX_LENGTH]
