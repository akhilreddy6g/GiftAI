"""The versioned public API: every route here requires sign-in and is rate limited."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from giftai.auth.dependencies import get_principal
from giftai.auth.tokens import AuthenticatedPrincipal
from giftai.catalog.router import router as catalog_router
from giftai.chats.router import router as chats_router
from giftai.core.errors import RateLimitedError
from giftai.core.rate_limit import RateLimiter
from giftai.feedback.router import router as feedback_router
from giftai.recipients.router import router as recipients_router
from giftai.rulebook.router import router as rulebook_router
from giftai.users.router import router as users_router

API_V1_PREFIX = "/api/v1"


def get_rate_limiter(request: Request) -> RateLimiter:
    limiter: RateLimiter = request.app.state.rate_limiter
    return limiter


async def enforce_rate_limit(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
) -> None:
    # Keyed on the verified token, before any database work, so a flood stays cheap.
    retry_after_seconds = limiter.acquire(str(principal.user_id))
    if retry_after_seconds is not None:
        raise RateLimitedError(retry_after_seconds)


api_router = APIRouter(prefix=API_V1_PREFIX, dependencies=[Depends(enforce_rate_limit)])
api_router.include_router(users_router)
api_router.include_router(recipients_router)
api_router.include_router(chats_router)
api_router.include_router(catalog_router)
api_router.include_router(rulebook_router)
api_router.include_router(feedback_router)
