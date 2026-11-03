"""Verification of the access tokens Supabase issues when a user signs in.

Supabase signs tokens with an asymmetric key and publishes the public half as a JSON Web
Key Set (JWKS). The API fetches that set, caches it, and checks every token's signature,
expiry, issuer and audience locally, so a request needs no call to Supabase.

The rest of the app depends only on ``TokenVerifier``, so another auth provider can be
swapped in by writing one class.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import httpx
import jwt
from jwt import PyJWK, PyJWKSet
from jwt.exceptions import PyJWKError, PyJWKSetError

from giftai.core.errors import ServiceUnavailableError, UnauthorizedError

logger = logging.getLogger(__name__)

# Only asymmetric algorithms: accepting HS* here would let a public key be used as a
# shared secret (the classic algorithm-confusion attack).
ALLOWED_ALGORITHMS = frozenset({"ES256", "RS256", "EdDSA"})


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Who a verified token says the caller is."""

    user_id: UUID
    email: str | None


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthenticatedPrincipal:
        """Return the token's principal, or raise ``UnauthorizedError``."""
        ...

    async def aclose(self) -> None: ...


class SigningKeySource(Protocol):
    async def get_key(self, key_id: str) -> PyJWK | None:
        """The public key with this id, or None if the issuer doesn't publish one."""
        ...

    async def aclose(self) -> None: ...


class RemoteJwks:
    """Fetches and caches a JWKS over HTTPS.

    Keys are refreshed after ``cache_seconds``, and early when a token names a key we
    haven't seen (the issuer may have rotated keys), but at most once per
    ``min_refresh_interval_seconds`` so bad tokens can't make us hammer the issuer.
    """

    def __init__(
        self,
        url: str,
        cache_seconds: int,
        http_client: httpx.AsyncClient | None = None,
        min_refresh_interval_seconds: float = 30.0,
    ) -> None:
        self._url = url
        self._cache_seconds = cache_seconds
        self._min_refresh_interval_seconds = min_refresh_interval_seconds
        self._http_client = http_client or httpx.AsyncClient(timeout=5.0)
        self._keys: dict[str, PyJWK] = {}
        self._fetched_at = float("-inf")
        self._lock = asyncio.Lock()

    async def get_key(self, key_id: str) -> PyJWK | None:
        if self._is_stale() or (key_id not in self._keys and self._may_refresh_early()):
            await self._refresh()
        return self._keys.get(key_id)

    async def aclose(self) -> None:
        await self._http_client.aclose()

    def _is_stale(self) -> bool:
        return time.monotonic() - self._fetched_at > self._cache_seconds

    def _may_refresh_early(self) -> bool:
        return time.monotonic() - self._fetched_at > self._min_refresh_interval_seconds

    async def _refresh(self) -> None:
        async with self._lock:
            # Another request may have refreshed while this one waited for the lock.
            if not self._is_stale() and not self._may_refresh_early():
                return
            try:
                response = await self._http_client.get(self._url)
                response.raise_for_status()
                key_set = PyJWKSet.from_dict(response.json())
            except (httpx.HTTPError, ValueError, PyJWKSetError) as error:
                if self._keys:
                    # Keep serving with the keys we have; Supabase may be briefly down.
                    logger.warning("Could not refresh signing keys; using cached keys: %s", error)
                    return
                raise ServiceUnavailableError(
                    "Sign-in is temporarily unavailable. Please try again in a minute."
                ) from error
            self._keys = {key.key_id: key for key in key_set.keys if key.key_id}
            self._fetched_at = time.monotonic()


class JwtTokenVerifier:
    def __init__(self, key_source: SigningKeySource, issuer: str, audience: str) -> None:
        self._key_source = key_source
        self._issuer = issuer
        self._audience = audience

    async def verify(self, token: str) -> AuthenticatedPrincipal:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as error:
            raise UnauthorizedError() from error

        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in ALLOWED_ALGORITHMS or not isinstance(key_id, str):
            raise UnauthorizedError()

        key = await self._key_source.get_key(key_id)
        if key is None:
            raise UnauthorizedError()

        try:
            claims = jwt.decode(
                token,
                key=key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "aud", "iss"]},
            )
            user_id = UUID(claims["sub"])
        except (jwt.InvalidTokenError, PyJWKError, ValueError) as error:
            raise UnauthorizedError(
                "Your session has expired. Please sign in again."
                if isinstance(error, jwt.ExpiredSignatureError)
                else None
            ) from error

        # Supabase can issue tokens to anonymous visitors; GiftAI requires a real account.
        if claims.get("is_anonymous") is True:
            raise UnauthorizedError()

        email = claims.get("email")
        return AuthenticatedPrincipal(
            user_id=user_id, email=email if isinstance(email, str) and email else None
        )

    async def aclose(self) -> None:
        await self._key_source.aclose()
