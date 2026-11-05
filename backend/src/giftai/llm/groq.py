import json
import logging

import httpx
from pydantic import ValidationError

from giftai.llm.base import LlmMessage, LlmUnavailableError, ResponseT

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


class GroqChatModel:
    """Groq's OpenAI-compatible API, used as the fallback. JSON mode plus the schema in
    the prompt, validated here, since strict schemas aren't supported on every model.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._transport = transport

    @property
    def name(self) -> str:
        return f"groq:{self._model}"

    async def generate(
        self, system: str, messages: list[LlmMessage], response_model: type[ResponseT]
    ) -> ResponseT:
        schema = json.dumps(response_model.model_json_schema())
        body = {
            "model": self._model,
            "temperature": 0.4,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": f"{system}\n\nReply with one JSON object matching this JSON "
                    f"schema, and nothing else:\n{schema}",
                },
                *({"role": m.role, "content": m.content} for m in messages),
            ],
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    _GROQ_URL, json=body, headers={"Authorization": f"Bearer {self._api_key}"}
                )
        except httpx.HTTPError as error:
            raise LlmUnavailableError(f"{self.name} failed: {type(error).__name__}") from error
        if response.status_code != 200:
            raise LlmUnavailableError(f"{self.name} returned {response.status_code}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return response_model.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            raise LlmUnavailableError(f"{self.name} returned malformed output") from error
