import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

import httpx
import pytest

from giftai.auth.tokens import RemoteJwks
from giftai.core.errors import ServiceUnavailableError, UnauthorizedError
from tests.auth_helpers import TEST_KEY_ID, TokenIssuer


async def test_a_valid_token_yields_its_user(token_issuer: TokenIssuer) -> None:
    user_id = uuid.uuid4()

    principal = await token_issuer.verifier.verify(token_issuer.issue(user_id, "a@b.co"))

    assert principal.user_id == user_id
    assert principal.email == "a@b.co"


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "someone-else"},
        {"iss": "https://evil.example/auth/v1"},
        {"is_anonymous": True},
        {"sub": "not-a-uuid"},
    ],
    ids=["wrong audience", "wrong issuer", "anonymous visitor", "malformed subject"],
)
async def test_tokens_with_bad_claims_are_rejected(
    token_issuer: TokenIssuer, claims: dict[str, Any]
) -> None:
    token = token_issuer.issue(**claims)

    with pytest.raises(UnauthorizedError):
        await token_issuer.verifier.verify(token)


async def test_expired_tokens_ask_the_user_to_sign_in_again(token_issuer: TokenIssuer) -> None:
    expired = token_issuer.issue(exp=int(time.time()) - 60)

    with pytest.raises(UnauthorizedError, match="expired"):
        await token_issuer.verifier.verify(expired)


async def test_tokens_signed_by_an_unknown_key_are_rejected(token_issuer: TokenIssuer) -> None:
    with pytest.raises(UnauthorizedError):
        await token_issuer.verifier.verify(TokenIssuer().issue())


async def test_symmetric_algorithms_are_refused(token_issuer: TokenIssuer) -> None:
    # Algorithm confusion: an attacker signs with HS256 using the public key as a secret.
    # PyJWT refuses to build such a token, so it is assembled by hand.
    def segment(data: dict[str, object]) -> bytes:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=")

    signing_input = (
        segment({"alg": "HS256", "typ": "JWT", "kid": TEST_KEY_ID})
        + b"."
        + segment(token_issuer.claims())
    )
    secret = json.dumps(token_issuer.public_jwk).encode()
    signature = base64.urlsafe_b64encode(
        hmac.new(secret, signing_input, hashlib.sha256).digest()
    ).rstrip(b"=")
    forged = (signing_input + b"." + signature).decode()

    with pytest.raises(UnauthorizedError):
        await token_issuer.verifier.verify(forged)


async def test_garbage_is_rejected(token_issuer: TokenIssuer) -> None:
    with pytest.raises(UnauthorizedError):
        await token_issuer.verifier.verify("not.a.token")


class _JwksServer:
    """A fake JWKS endpoint that counts requests and can be switched to failing."""

    def __init__(self, jwk: dict[str, object]) -> None:
        self.jwk = jwk
        self.requests = 0
        self.failing = False

    def handle(self, _: httpx.Request) -> httpx.Response:
        self.requests += 1
        if self.failing:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": [self.jwk]})

    def jwks(self, **options: float) -> RemoteJwks:
        client = httpx.AsyncClient(transport=httpx.MockTransport(self.handle))
        return RemoteJwks("https://jwks.test", http_client=client, **options)  # type: ignore[arg-type]


async def test_keys_are_cached_between_requests(token_issuer: TokenIssuer) -> None:
    server = _JwksServer(token_issuer.public_jwk)
    jwks = server.jwks(cache_seconds=600)

    assert await jwks.get_key(TEST_KEY_ID) is not None
    assert await jwks.get_key(TEST_KEY_ID) is not None
    assert server.requests == 1


async def test_unknown_key_ids_cannot_force_constant_refetching(
    token_issuer: TokenIssuer,
) -> None:
    server = _JwksServer(token_issuer.public_jwk)
    jwks = server.jwks(cache_seconds=600, min_refresh_interval_seconds=30)

    await jwks.get_key(TEST_KEY_ID)
    for _ in range(5):
        assert await jwks.get_key("rotated-key") is None
    assert server.requests == 1


async def test_cached_keys_survive_an_issuer_outage(token_issuer: TokenIssuer) -> None:
    server = _JwksServer(token_issuer.public_jwk)
    jwks = server.jwks(cache_seconds=0, min_refresh_interval_seconds=0)
    await jwks.get_key(TEST_KEY_ID)

    server.failing = True

    assert await jwks.get_key(TEST_KEY_ID) is not None


async def test_an_outage_before_any_keys_is_reported_as_unavailable(
    token_issuer: TokenIssuer,
) -> None:
    server = _JwksServer(token_issuer.public_jwk)
    server.failing = True

    with pytest.raises(ServiceUnavailableError):
        await server.jwks(cache_seconds=600).get_key(TEST_KEY_ID)
