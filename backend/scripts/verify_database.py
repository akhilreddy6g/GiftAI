"""Check that a Postgres database can host GiftAI before pointing the app at it.

Usage:
    DATABASE_URL='postgres://user:pass@host:port/db?sslmode=require' \
        uv run python scripts/verify_database.py

Everything runs inside one transaction that is rolled back, so the database is left exactly
as it was, apart from the vector extension, which is kept once created (the first
migration needs it anyway). Exits non-zero if any check fails.
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass

import psycopg

from giftai.core.config import get_database_settings

MINIMUM_SERVER_VERSION = 150000  # Postgres 15
# The catalog stores 384-dimension half-precision vectors (bge-small-en-v1.5).
EMBEDDING_DIMENSIONS = 384


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


Check = Callable[[psycopg.Connection], CheckResult]


def check_server_version(connection: psycopg.Connection) -> CheckResult:
    version = connection.info.server_version
    readable = f"{version // 10000}.{version % 10000}"
    return CheckResult(
        "Postgres version", version >= MINIMUM_SERVER_VERSION, f"{readable} (need 15 or newer)"
    )


def check_vector_extension(connection: psycopg.Connection) -> CheckResult:
    connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
    row = connection.execute(
        "SELECT extversion FROM pg_extension WHERE extname = 'vector'"
    ).fetchone()
    if row is None:
        return CheckResult("pgvector extension", False, "not installed after CREATE EXTENSION")
    # halfvec (half precision) arrived in pgvector 0.7; it halves the catalog's storage.
    major, minor, *_ = (int(part) for part in str(row[0]).split("."))
    return CheckResult(
        "pgvector extension", (major, minor) >= (0, 7), f"version {row[0]} (need 0.7 or newer)"
    )


def check_halfvec_index(connection: psycopg.Connection) -> CheckResult:
    connection.execute(
        f"CREATE TEMP TABLE giftai_vector_probe (embedding halfvec({EMBEDDING_DIMENSIONS}))"
    )
    connection.execute(
        "CREATE INDEX ON giftai_vector_probe USING hnsw (embedding halfvec_cosine_ops)"
    )
    probe = "[" + ",".join(["0.1"] * EMBEDDING_DIMENSIONS) + "]"
    connection.execute("INSERT INTO giftai_vector_probe VALUES (%s::halfvec)", (probe,))
    nearest = connection.execute(
        "SELECT embedding <=> %s::halfvec FROM giftai_vector_probe LIMIT 1", (probe,)
    ).fetchone()
    passed = nearest is not None and abs(float(nearest[0])) < 1e-3
    return CheckResult("halfvec + HNSW index", passed, "cosine search returned the probe row")


def check_storage(connection: psycopg.Connection) -> CheckResult:
    row = connection.execute(
        "SELECT pg_size_pretty(pg_database_size(current_database()))"
    ).fetchone()
    return CheckResult("Current database size", True, str(row[0]) if row else "unknown")


CHECKS: tuple[Check, ...] = (
    check_server_version,
    check_vector_extension,
    check_halfvec_index,
    check_storage,
)


def run_checks(database_url: str) -> list[CheckResult]:
    with psycopg.connect(database_url, connect_timeout=15) as connection:
        results = []
        for check in CHECKS:
            try:
                results.append(check(connection))
            except psycopg.Error as error:
                connection.rollback()
                results.append(CheckResult(check.__name__, False, str(error).strip()))
        # The extension is committed separately so the probe table never persists.
        connection.rollback()
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        connection.commit()
    return results


def main() -> int:
    database_url = get_database_settings().database_url.get_secret_value()
    try:
        results = run_checks(database_url)
    except psycopg.OperationalError as error:
        print(f"FAIL  Could not connect: {str(error).strip()}")
        return 1

    for result in results:
        print(f"{'PASS' if result.passed else 'FAIL'}  {result.name}: {result.detail}")
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
