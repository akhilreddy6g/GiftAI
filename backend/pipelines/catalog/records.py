"""The selected product, as the select step writes it and later steps read it."""

import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CatalogProduct:
    asin: str
    title: str
    brand: str | None
    main_category: str
    category_path: tuple[str, ...]
    price: Decimal
    rating_average: float
    rating_count: int
    image_url: str
    short_description: str | None
    # Used for the embedding text only; not stored in the database.
    features: tuple[str, ...]
    last_reviewed_on: date

    def to_json(self) -> str:
        data: dict[str, Any] = asdict(self)
        data["price"] = str(self.price)
        data["last_reviewed_on"] = self.last_reviewed_on.isoformat()
        return json.dumps(data, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "CatalogProduct":
        data = json.loads(line)
        return cls(
            asin=data["asin"],
            title=data["title"],
            brand=data["brand"],
            main_category=data["main_category"],
            category_path=tuple(data["category_path"]),
            price=Decimal(data["price"]),
            rating_average=float(data["rating_average"]),
            rating_count=int(data["rating_count"]),
            image_url=data["image_url"],
            short_description=data["short_description"],
            features=tuple(data["features"]),
            last_reviewed_on=date.fromisoformat(data["last_reviewed_on"]),
        )


def write_products(path: Path, products: Iterable[CatalogProduct], append: bool = False) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a" if append else "w", encoding="utf-8") as file:
        for product in products:
            file.write(product.to_json() + "\n")
            count += 1
    return count


def read_products(path: Path) -> Iterator[CatalogProduct]:
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                yield CatalogProduct.from_json(line)
