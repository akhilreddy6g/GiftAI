"""A miniature Amazon Reviews 2023 dataset with two clear tastes: coffee and yoga.

Thirty reviewers like coffee gear, thirty like yoga gear, so ALS should learn that coffee
products go together and yoga products go together. A few records break one selection
rule each, so the select step has something to reject.
"""

import csv
import gzip
import json
from datetime import UTC, datetime
from typing import Any

from pipelines.catalog.workspace import Workspace

CATEGORY = "Home_and_Kitchen"

COFFEE = {
    "B000COFFE1": "Pour-Over Coffee Kit with Glass Carafe",
    "B000COFFE2": "Manual Coffee Grinder with Ceramic Burr",
    "B000COFFE3": "Gooseneck Coffee Kettle",
    "B000COFFE4": "Insulated Coffee Travel Mug",
    "B000COFFE5": "Single Origin Coffee Beans Sampler",
}
YOGA = {
    "B000YOGAM1": "Non-Slip Yoga Mat",
    "B000YOGAM2": "Cork Yoga Blocks, Set of Two",
    "B000YOGAM3": "Yoga Strap for Stretching",
    "B000YOGAM4": "Meditation Cushion for Yoga",
    "B000YOGAM5": "Yoga Towel, Quick Dry",
}
# Each breaks exactly one rule.
REJECTED: dict[str, dict[str, Any]] = {
    "B000NOPRCE": {"price": None},
    "B000LOWRAT": {"average_rating": 2.9},
    "B000FEWRAT": {"rating_number": 3},
    "B000OLDREV": {},  # its only reviews are from 2019
    "B000PARTS1": {"categories": ["Home & Kitchen", "Replacement Parts"]},
}
OLD_REVIEW_ASIN = "B000OLDREV"


def write_sample_dataset(workspace: Workspace) -> None:
    workspace.raw_dir.mkdir(parents=True, exist_ok=True)
    records = [
        _meta(asin, title, price=20 + index)
        for index, (asin, title) in enumerate({**COFFEE, **YOGA}.items())
    ]
    records += [
        _meta(asin, "Gift Item " + asin, price=25) | overrides
        for asin, overrides in REJECTED.items()
    ]
    with gzip.open(workspace.meta_file(CATEGORY), "wt", encoding="utf-8") as file:
        file.write("not json\n")
        for record in records:
            file.write(json.dumps(record) + "\n")

    with gzip.open(workspace.ratings_file(CATEGORY), "wt", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["user_id", "parent_asin", "rating", "timestamp"])
        for user in range(60):
            liked = list(COFFEE if user < 30 else YOGA)
            # Each reviewer likes four of their five products, a different four each time.
            for offset, asin in enumerate(liked[user % 5 :] + liked[: user % 5]):
                if offset < 4:
                    writer.writerow([f"U{user:03d}", asin, 5, _millis(2023, 1 + offset)])
        for asin in REJECTED:
            year = 2019 if asin == OLD_REVIEW_ASIN else 2023
            writer.writerow(["U999", asin, 5, _millis(year, 3)])


def _meta(asin: str, title: str, price: float) -> dict[str, Any]:
    return {
        "main_category": "Amazon Home",
        "title": title,
        "average_rating": 4.6,
        "rating_number": 1200,
        "features": [f"Great {title.lower()}", "Gift ready packaging"],
        "description": [f"A lovely {title.lower()}."],
        "price": price,
        "images": [
            {"thumb": "https://m.media-amazon.com/t.jpg", "variant": "PT01"},
            {"large": f"https://m.media-amazon.com/{asin}.jpg", "variant": "MAIN"},
        ],
        "store": "Acme",
        "categories": ["Home & Kitchen", "Kitchen & Dining"],
        "details": {},
        "parent_asin": asin,
    }


def _millis(year: int, month: int) -> int:
    return int(datetime(year, month, 15, tzinfo=UTC).timestamp() * 1000)
