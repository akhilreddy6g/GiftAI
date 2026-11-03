"""Issues real signed tokens for tests, standing in for Supabase.

Tests go through the production ``JwtTokenVerifier``; only the source of public keys is
replaced, so signature, expiry, issuer and audience checks all run for real.
"""

import json
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm

from giftai.auth.tokens import JwtTokenVerifier

TEST_SUPABASE_URL = "https://test-project.supabase.co"
TEST_ISSUER = f"{TEST_SUPABASE_URL}/auth/v1"
TEST_AUDIENCE = "authenticated"
TEST_KEY_ID = "test-key-1"


class StaticKeySource:
    def __init__(self, keys: dict[str, PyJWK]) -> None:
        self._keys = keys

    async def get_key(self, key_id: str) -> PyJWK | None:
        return self._keys.get(key_id)

    async def aclose(self) -> None:
        return None


class TokenIssuer:
    def __init__(self) -> None:
        self._private_key = ec.generate_private_key(ec.SECP256R1())
        public_jwk = json.loads(ECAlgorithm.to_jwk(self._private_key.public_key()))
        public_jwk.update({"kid": TEST_KEY_ID, "alg": "ES256", "use": "sig"})
        self.public_jwk: dict[str, Any] = public_jwk
        self.verifier = JwtTokenVerifier(
            StaticKeySource({TEST_KEY_ID: PyJWK(public_jwk)}),
            issuer=TEST_ISSUER,
            audience=TEST_AUDIENCE,
        )

    def issue(
        self,
        user_id: uuid.UUID | None = None,
        email: str | None = "giver@example.com",
        key_id: str = TEST_KEY_ID,
        **claim_overrides: Any,
    ) -> str:
        claims = self.claims(user_id, email, **claim_overrides)
        return jwt.encode(claims, self._private_key, algorithm="ES256", headers={"kid": key_id})

    def claims(
        self,
        user_id: uuid.UUID | None = None,
        email: str | None = "giver@example.com",
        **claim_overrides: Any,
    ) -> dict[str, Any]:
        """The claims Supabase would put in a token for this user."""
        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": str(user_id or uuid.uuid4()),
            "email": email,
            "aud": TEST_AUDIENCE,
            "iss": TEST_ISSUER,
            "iat": now,
            "exp": now + 3600,
            "role": "authenticated",
        }
        return claims | claim_overrides

    def headers_for(self, user_id: uuid.UUID) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.issue(user_id)}"}
