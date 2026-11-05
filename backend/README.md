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
  agent/       the gift assistant: LangGraph turn, candidates, ranking, picks
  llm/         the LLM interface: Gemini first, Groq as fallback
  catalog/     products, meaning search and "also liked" (/api/v1/products)
  rulebook/    the gifting rulebook (/api/v1/rules)
  embeddings/  the text-embedding interface and its bge-small implementation
  health/      liveness and readiness endpoints
  gifting.py   shared vocabulary: relationships and occasions
  api.py       the /api/v1 router: sign-in and rate limit on every route
  main.py      application factory
migrations/    Alembic migrations (the only way the schema changes)
scripts/       operational scripts: verify a database, get an access token
pipelines/     offline jobs run on a laptop, never deployed (catalog/, rulebook/)
rulebook/      the approved gifting rules, loaded by `pipelines.rulebook seed`
tests/         unit/, catalog_pipeline/, rulebook_pipeline/ (no database), api/ (real Postgres)
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

## The gift assistant

`POST /api/v1/chats/{id}/messages` runs one turn of the assistant and returns the user's
message, the reply, any gift picks, an `add_all_to_cart_url`, the `order_by` date and the
chat as the assistant left it (it fills in occasion, date and budget as it learns them,
and retitles the chat unless the user named it).

Each turn is a small LangGraph graph (`agent/graph.py`):

1. **Understand.** The LLM reads the conversation and updates the recipient profile:
   relationship, occasion, date, budget, interests, personality, things to avoid. The
   chat's own fields and the saved person, if any, are folded in first.
2. **Ask or suggest.** While key details are missing it asks one question, at most 4 in
   all; it suggests sooner if the user asks for ideas.
3. **Candidates.** Meaning search for each of the LLM's product queries, plus the "also
   liked" neighbors of the best hits, within about the budget: up to a few hundred products.
4. **Rank.** A hand-set score (relevance, fit to budget, rating, review count; products
   already shown drop back) keeps the best 20, at most 3 of a kind.
5. **Pick and explain.** The LLM chooses 5 or 6 from those 20 with the gifting rules that
   apply, says why each suits the person and which rules it follows. Products and rule
   ids are checked against what was offered; anything else is dropped.

`GET /api/v1/chats/{id}/recommendations` returns the latest picks again, or the picks of
the replies named by `message_id` (repeat it, up to 50), so a reopened chat can show each
reply's gifts under it. Every pick carries its `message_id`, the user's `rating` and the
product's `availability`; `add_all_to_cart_urls` has one cart link per reply. A turn's message
and reply are saved together only when the assistant has answered, so if both LLMs are
busy (503) nothing is half-saved and the user just sends again.

Set `GEMINI_API_KEY` (and optionally `GROQ_API_KEY` as the fallback) in `backend/.env`, or
in the repo-root `.env` for Docker Compose. Without either, chats work but the assistant
replies that it is switched off. Each user gets `AGENT_TURNS_PER_USER_PER_DAY` replies a day
(default 40), since the free LLM quotas are shared by everyone.

## Products

| Endpoint                                   | What it returns                                  |
|--------------------------------------------|--------------------------------------------------|
| `GET /api/v1/products/search?q=`           | Products closest in meaning to `q`, best first. Optional `limit` (max 50), `min_price`, `max_price` in whole dollars. |
| `GET /api/v1/products/{asin}`              | One product                                      |
| `GET /api/v1/products/{asin}/also-liked`   | Products liked by the same reviewers (`limit`, max 20) |

Every product carries `amazon_url` and `amazon_search_url` (a search for its name, for when
the listing has gone). Prices are 2023 prices from the dataset, so `price_2023` says so.

## Feedback and availability

| Endpoint                                     | What it does |
|----------------------------------------------|--------------|
| `POST /api/v1/feedback/events`               | Logs `clicked` or `added_to_cart` for 1 to 10 of the user's picks (204). All or nothing: any pick that isn't theirs gives 404 |
| `PUT /api/v1/recommendations/{id}/rating`    | Thumbs `up`, `down` or `null` to clear (204). Each change is logged as an event |
| `PUT /api/v1/products/{asin}/availability`   | The user's answer to "Did you find it on Amazon?" (`found`), one vote per user and product; returns the product's availability |

A product's availability is `verified` when most voters found it, `likely_gone` when most
didn't, and `unverified` on a tie or with no votes. Likely gone products still appear, but
their ranking score is quartered (`feedback/availability.py`), so they sink below the rest.

## Gifting rules

| Endpoint                     | What it returns                                                  |
|------------------------------|------------------------------------------------------------------|
| `GET /api/v1/rules`          | Active rules that apply to a situation. Optional `relationship`, `occasion`, `budget_min`, `budget_max` (whole dollars). Rules tagged for no relationship or occasion apply to all; budget-limited rules apply when their range overlaps the budget |
| `GET /api/v1/rules/{rule_id}`| One rule, such as `R-012`, with the sources it cites (also retired ones, for old recommendations) |

Relationships and occasions use the same values as recipients and chats (`giftai/gifting.py`).

## Building the rulebook

The rules are ours: drafted by an LLM from books and papers, then approved, edited or
rejected by a person. Only `rulebook/rulebook.yaml` (the rules and their citations) is
committed; the sources and anything drawn from their text stay in `backend/data/rulebook/`,
which git ignores.

| Step      | What it does                                                                 |
|-----------|------------------------------------------------------------------------------|
| `scan`    | Adds an entry to `data/rulebook/sources.yaml` for each new file in `data/rulebook/`, with the title, authors and year read from the file's metadata (PDF info, EPUB metadata), and papers told apart from books by length. Check the guesses; missing ones are marked `TODO` |
| `extract` | Splits each file in `data/rulebook/sources.yaml` into sections: PDFs by their bookmarks (or every 12 pages), EPUBs by reading order, text and Markdown by headings |
| `draft`   | Asks Gemini (free tier, about 8 requests a minute) for up to 8 candidate rules per section, in its own words. Resumable: sections already drafted are skipped |
| `group`   | Groups drafts that say the same thing (bge-small similarity), so each idea is reviewed once and cites every source behind it |
| `review`  | Interactive: accept a wording, edit it in `$EDITOR`, reject or skip. Saves after every decision; run it again to carry on |
| `seed`    | Loads `rulebook/rulebook.yaml` into the database in `DATABASE_URL` in one transaction. Rules removed from the file are retired, not deleted |

```bash
cd backend
mkdir -p data/rulebook   # put the files here, in subfolders if you like
uv run python -m pipelines.rulebook scan      # then check data/rulebook/sources.yaml
uv run python -m pipelines.rulebook extract
echo 'GEMINI_API_KEY=...' >> .env
uv run python -m pipelines.rulebook draft
uv run python -m pipelines.rulebook group
uv run python -m pipelines.rulebook review
uv run python -m pipelines.rulebook seed      # then commit rulebook/rulebook.yaml
```

`--sources ID ...` limits `extract`, `draft` and `review` to some sources. Scanned PDFs
have no text layer and need OCR first.

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

## The API contract

The frontend's TypeScript types are generated from this API's OpenAPI schema. After
changing a request or response shape, regenerate them from `frontend/` with
`npm run api:sync` and commit the result; CI fails while they are out of date.

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
