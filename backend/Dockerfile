# syntax=docker/dockerfile:1

# ---- Build: resolve and install dependencies into a virtualenv with uv -------------------
FROM python:3.13-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv

WORKDIR /app

# Dependencies first, so this layer is cached until the lockfile changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-install-project

COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-editable

# Bake the search embedding model into the image, so the server never downloads at runtime.
ARG EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
RUN /app/.venv/bin/python -c "import sys; from fastembed import TextEmbedding; \
TextEmbedding(sys.argv[1], cache_dir='/app/models')" "$EMBEDDING_MODEL_NAME"

# ---- Runtime: only the virtualenv, migrations and scripts, run as a non-root user --------
FROM python:3.13-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    EMBEDDING_CACHE_DIR=/app/models \
    PORT=8000

RUN groupadd --system giftai && useradd --system --gid giftai --no-create-home giftai

WORKDIR /app
COPY --from=build --chown=giftai:giftai /app/.venv ./.venv
COPY --from=build --chown=giftai:giftai /app/models ./models
COPY --chown=giftai:giftai alembic.ini ./
COPY --chown=giftai:giftai migrations ./migrations
COPY --chown=giftai:giftai scripts ./scripts

USER giftai
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health/live', timeout=4)"]

# Render injects PORT; exec keeps uvicorn as PID 1 so it receives stop signals.
# Access logs are off because RequestIdMiddleware logs every request with its id and timing.
CMD ["sh", "-c", "exec uvicorn giftai.main:create_app --factory --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
