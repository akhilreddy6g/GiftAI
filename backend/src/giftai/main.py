"""Builds the FastAPI application: settings, logging, middleware, errors and routes."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from giftai.api import api_router
from giftai.auth.tokens import JwtTokenVerifier, RemoteJwks, TokenVerifier
from giftai.core.config import Settings, get_settings
from giftai.core.errors import ErrorResponse, register_error_handlers
from giftai.core.logging import configure_logging
from giftai.core.middleware import BodySizeLimitMiddleware, RequestIdMiddleware
from giftai.core.rate_limit import FixedWindowRateLimiter
from giftai.core.request_context import REQUEST_ID_HEADER
from giftai.db.session import Database
from giftai.health.router import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.database = Database(settings)
        app.state.token_verifier = build_token_verifier(settings)
        app.state.rate_limiter = FixedWindowRateLimiter(
            limit=settings.rate_limit_requests_per_minute, window_seconds=60
        )
        try:
            yield
        finally:
            await app.state.token_verifier.aclose()
            await app.state.database.dispose()

    app = FastAPI(
        title="GiftAI API",
        version="0.1.0",
        lifespan=lifespan,
        # Every documented endpoint can fail with the shared error envelope.
        responses={"default": {"model": ErrorResponse}},
        # Interactive docs are a development aid, not part of the public surface.
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
    )

    register_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_body_bytes)
    # Added last so it runs first and every log line, CORS rejections included, has an id.
    app.add_middleware(RequestIdMiddleware)

    app.include_router(health_router)
    app.include_router(api_router)
    return app


def build_token_verifier(settings: Settings) -> TokenVerifier:
    key_source = RemoteJwks(settings.supabase_jwks_url, settings.supabase_jwks_cache_seconds)
    return JwtTokenVerifier(
        key_source, issuer=settings.supabase_auth_issuer, audience=settings.supabase_jwt_audience
    )
