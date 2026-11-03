"""FastAPI dependencies that authenticate the caller and load their account."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from giftai.auth.tokens import AuthenticatedPrincipal, TokenVerifier
from giftai.core.errors import UnauthorizedError
from giftai.users.dependencies import UserServiceDep
from giftai.users.models import User

# auto_error=False so a missing header gets our error envelope, not FastAPI's default.
_bearer_scheme = HTTPBearer(auto_error=False, description="Supabase access token")


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


async def get_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
) -> AuthenticatedPrincipal:
    if credentials is None:
        raise UnauthorizedError()
    return await verifier.verify(credentials.credentials)


async def get_current_user(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_principal)],
    users: UserServiceDep,
) -> User:
    return await users.ensure_account(principal)


CurrentUser = Annotated[User, Depends(get_current_user)]
