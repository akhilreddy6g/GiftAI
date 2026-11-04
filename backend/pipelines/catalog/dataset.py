"""The Amazon Reviews 2023 dataset (McAuley Lab, UC San Diego): where its files live and
how to stream them without loading a multi-gigabyte file into memory.

Two files per category are used:
- metadata (``meta_<Category>.jsonl.gz``): one product per line, keyed by ``parent_asin``.
- 5-core ratings (``<Category>.csv.gz``): ``user_id,parent_asin,rating,timestamp`` rows,
  limited to users and products with at least five reviews each.
"""

import csv
import gzip
import io
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

DATASET_BASE_URL = "https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023"


def meta_url(category: str) -> str:
    return f"{DATASET_BASE_URL}/raw/meta_categories/meta_{category}.jsonl.gz"


def ratings_url(category: str) -> str:
    return f"{DATASET_BASE_URL}/benchmark/5core/rating_only/{category}.csv.gz"


@dataclass(frozen=True)
class Rating:
    user_id: str
    asin: str
    rating: float
    reviewed_at: datetime

    @property
    def reviewed_on(self) -> date:
        return self.reviewed_at.date()


def download(url: str, destination: Path) -> None:
    """Fetch ``url`` to ``destination`` unless it's already there; partial files never
    take the final name, so an interrupted download simply starts again.
    """
    if destination.exists():
        logger.info("Already downloaded: %s", destination.name)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_name(destination.name + ".part")
    logger.info("Downloading %s", url)
    timeout = httpx.Timeout(30.0, read=120.0)
    with (
        httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response,
        partial.open("wb") as file,
    ):
        response.raise_for_status()
        total = int(response.headers.get("Content-Length", 0))
        received = 0
        next_report = 0.0
        for chunk in response.iter_bytes(chunk_size=1 << 20):
            file.write(chunk)
            received += len(chunk)
            if total and received / total >= next_report:
                logger.info(
                    "  %s: %3.0f%% of %.0f MB",
                    destination.name,
                    100 * received / total,
                    total / 1e6,
                )
                next_report += 0.1
    partial.rename(destination)


def iter_metadata(path: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(path, mode="rt", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed line %d in %s", line_number, path.name)
                continue
            if isinstance(record, dict):
                yield record


def iter_ratings(path: Path) -> Iterator[Rating]:
    with gzip.open(path, mode="rb") as raw, io.TextIOWrapper(raw, encoding="utf-8") as file:
        for row in csv.DictReader(file):
            try:
                yield Rating(
                    user_id=row["user_id"],
                    asin=row["parent_asin"],
                    rating=float(row["rating"]),
                    # The dataset's timestamps are Unix milliseconds.
                    reviewed_at=datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC),
                )
            except (KeyError, ValueError):
                continue
