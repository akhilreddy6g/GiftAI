# GiftAI backend

FastAPI service behind the GiftAI web app. See the [root README](../README.md) for the
project overview and the one-command local setup.

## Layout

```
src/giftai/
  core/        cross-cutting plumbing: settings, logging, errors, middleware
  db/          SQLAlchemy base and session lifecycle
  health/      liveness and readiness endpoints
  main.py      application factory
migrations/    Alembic migrations (the only way the schema changes)
scripts/       operational scripts, e.g. verifying a new database
tests/         unit/ (no I/O) and api/ (against a real Postgres)
```

Each feature lives in its own package with the same shape: `router.py` (HTTP only),
`service.py` (business logic), `schemas.py` (Pydantic request and response models), and,
once it stores data, `models.py` and `repository.py`.

## Working on it without Docker

Requires [uv](https://docs.astral.sh/uv/) and a Postgres with pgvector (the Compose `db`
service is the easiest one).

```bash
uv sync                                  # install dependencies into .venv
cp ../.env.example .env                  # then fill in DATABASE_URL
uv run alembic upgrade head              # build the schema
uv run uvicorn giftai.main:create_app --factory --reload
```

## Checks (the same ones CI runs)

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
TEST_DATABASE_URL=postgresql://giftai:giftai@localhost:5432/giftai_test uv run pytest
```

API tests are skipped when `TEST_DATABASE_URL` is unset. They drop and recreate the schema
in that database, so never point it at a database you care about.

## Verifying a hosted database

Before first use of a new database (for example the Aiven free plan), run:

```bash
DATABASE_URL='postgres://...' uv run python scripts/verify_database.py
```

It checks the connection, the Postgres version, that pgvector can be enabled, and that a
half-precision vector index works, then reports each result.
