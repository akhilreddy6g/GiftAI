# GiftAI backend

FastAPI service behind the GiftAI web app. See the [root README](../README.md) for the
project overview and the one-command local setup.

## Layout

```
src/giftai/
  core/        cross-cutting plumbing: settings, logging, errors, middleware,
               pagination, rate limiting, input validation types
  db/          SQLAlchemy base, shared column types, session lifecycle, keyset paging
  auth/        Supabase token verification and the current-user dependency
  users/       accounts (GET/DELETE /api/v1/me)
  recipients/  people a user shops for (/api/v1/recipients)
  chats/       chats and their messages (/api/v1/chats)
  catalog/     products, meaning search and "also liked" (/api/v1/products)
  embeddings/  the text-embedding interface and its bge-small implementation
  health/      liveness and readiness endpoints
  gifting.py   shared vocabulary: relationships and occasions
  api.py       the /api/v1 router: sign-in and rate limit on every route
  main.py      application factory
migrations/    Alembic migrations (the only way the schema changes)
scripts/       operational scripts: verify a database, get an access token
pipelines/     offline jobs run on a laptop, never deployed (catalog/: the product catalog)
tests/         unit/ and catalog_pipeline/ (no database), api/ (against a real Postgres)
```

Each feature package has the same shape:

| File              | Responsibility                                              |
|-------------------|-------------------------------------------------------------|
| `router.py`       | HTTP only: parse the request, call the service, shape output |
| `service.py`      | Business rules, ownership checks, transactions              |
| `repository.py`   | Database queries for the feature's tables                   |
| `models.py`       | SQLAlchemy tables                                           |
| `schemas.py`      | Pydantic request and response models                        |
| `dependencies.py` | FastAPI providers for the feature's service                 |

## API conventions

- **Auth:** every `/api/v1` route needs `Authorization: Bearer <Supabase access token>`.
  The account row is created on the user's first request.
- **Errors:** always `{"error": {"code", "message", "request_id"}}`; `message` is safe to
  show to users.
- **Lists:** `?limit=` (max 50) and `?cursor=`; responses are
  `{"items": [...], "next_cursor": "..." | null}`, newest first.
- **Updates:** `PATCH` changes only the fields sent; sending `null` clears an optional field.
- **Ownership:** another user's resource answers 404, never 403, so ids don't leak.
- **Abuse protection:** 60 requests per minute per user (429 with `Retry-After`), 64 KB
  request bodies (413), length caps on every text field, and per-account storage caps.

## Products

| Endpoint                                   | What it returns                                  |
|--------------------------------------------|--------------------------------------------------|
| `GET /api/v1/products/search?q=`           | Products closest in meaning to `q`, best first. Optional `limit` (max 50), `min_price`, `max_price` in whole dollars. |
| `GET /api/v1/products/{asin}`              | One product                                      |
| `GET /api/v1/products/{asin}/also-liked`   | Products liked by the same reviewers (`limit`, max 20) |

Every product carries `amazon_url` and `amazon_search_url` (a search for its name, for when
the listing has gone). Prices are 2023 prices from the dataset, so `price_2023` says so.

## Building the product catalog

The catalog comes from the [Amazon Reviews 2023](https://amazon-reviews-2023.github.io/)
dataset. The pipeline runs on your machine; the dataset files never enter the repo, the
server or the database.

| Step        | What it does                                                                 |
|-------------|------------------------------------------------------------------------------|
| `download`  | Fetches each category's product metadata and 5-core ratings into `backend/data/catalog/raw/` (skips files already there) |
| `select`    | Keeps good gifts: price $5 to $500, 50+ ratings, 3.8+ stars, an image, reviewed since Sept 2022, no replacement parts and the like. Takes the most-reviewed per category, about 85,000 in total |
| `embed`     | Embeds each product's title, brand, category and features with bge-small (the same model search uses) |
| `neighbors` | Trains ALS on who liked what (4+ stars), reports Recall@10 and @50 against a popularity baseline, and keeps each product's top 20 "also liked" |
| `load`      | Upserts products and replaces neighbor lists in the database in `DATABASE_URL`, in one transaction |

```bash
docker compose up --build           # from the repo root: the local database, migrated
cd backend
uv sync                             # includes the pipeline's extras
export DATABASE_URL=postgresql://giftai:giftai@localhost:5432/giftai
# a quick trial on one smaller category:
uv run python -m pipelines.catalog all --categories Musical_Instruments --scale 0.5
# the full catalog (downloads several GB; embedding takes a while on a laptop CPU):
uv run python -m pipelines.catalog all
# load the same files into Aiven (run `alembic upgrade head` against it first):
DATABASE_URL='postgres://...' uv run python -m pipelines.catalog load
```

The first `embed` downloads the bge-small model (about 70 MB).

Each step reads the previous step's files, so you can re-run any single step, for example
`neighbors` with `--als-factors 128`. The evaluation lands in
`backend/data/catalog/neighbors_report.json`; ALS should clearly beat the popularity
baseline. Re-loading is safe: products dropped from a new catalog are kept but taken out of
search (`in_catalog = false`), because past recommendations may point at them.

Category quotas and selection rules live in `pipelines/catalog/config.py`.

## Calling the API by hand

Create a user under Authentication > Users in your Supabase dashboard, then:

```bash
export SUPABASE_URL=https://<project>.supabase.co SUPABASE_ANON_KEY=<publishable key>
TOKEN=$(uv run python scripts/get_access_token.py you@example.com)
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/me
```

## Working on it without Docker

Requires [uv](https://docs.astral.sh/uv/) and a Postgres with pgvector (the Compose `db`
service is the easiest one).

```bash
uv sync                                  # install dependencies into .venv
cp ../.env.example .env                  # then fill in DATABASE_URL
uv run alembic upgrade head              # build the schema
# new migration after changing a model (use the next number as the id):
# uv run alembic revision --autogenerate --rev-id 0005 -m "Describe the change"
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
