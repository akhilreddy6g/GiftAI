# GiftAI

GiftAI is an agentic gift recommender for Amazon US. You describe who you're shopping for,
it asks a few good questions, then researches, ranks and explains a short list of gifts and
fills your Amazon cart with one tap. You place the order on Amazon yourself.

Recommendations come from a curated subset of the Amazon Reviews 2023 dataset, ranked by a
multi-stage pipeline (semantic search plus collaborative filtering, then a ranker) and
guided by a gifting rulebook distilled from books and research on gift giving.

## Repository layout

```
backend/     FastAPI service, Alembic migrations, tests   (see backend/README.md)
frontend/    Angular app                                  (coming in a later milestone)
.github/     CI workflows
```

## Run it locally

Requires Docker and a free [Supabase](https://supabase.com) project (used only for sign-in).

```bash
cp .env.example .env      # then set SUPABASE_URL and SUPABASE_ANON_KEY
docker compose up --build
```

This starts Postgres with pgvector, applies the migrations, and serves the API on
http://localhost:8000. Check it with:

```bash
curl http://localhost:8000/health/ready
# {"status":"ok","database":"ok","vector_extension":"ok"}
```

Interactive API docs are at http://localhost:8000/docs (disabled in production).

Every `/api/v1` endpoint needs a Supabase access token. Until the frontend exists, get one
for a test user with `backend/scripts/get_access_token.py` (see the backend README).

## Configuration

All settings come from environment variables; [.env.example](.env.example) lists every one
with an explanation. Secrets never go in the repository: locally they live in a git-ignored
`.env`, and in deployment they live in the host's environment variables and GitHub Actions
secrets.

## Stack

| Part        | Choice                                                         |
|-------------|----------------------------------------------------------------|
| Backend     | Python 3.13, FastAPI, SQLAlchemy 2 (async), Alembic            |
| Database    | PostgreSQL with pgvector (Aiven free plan in production)       |
| Auth        | Supabase Auth (sign-in only; app data stays in our database)   |
| Agent / LLM | LangGraph, Gemini Flash with Groq as fallback                  |
| Embeddings  | bge-small-en-v1.5 via fastembed                                |
| Frontend    | Angular, Tailwind CSS                                          |
| Hosting     | Render (backend), Vercel (frontend), all on free tiers         |
