import logging

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from giftai.llm.base import LlmMessage, LlmUnavailableError, ResponseT

logger = logging.getLogger(__name__)


class GeminiChatModel:
    """Google Gemini through its official SDK, with JSON output constrained to a schema."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30) -> None:
        self._client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout_seconds * 1000)),
        )
        self._model = model

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    async def generate(
        self, system: str, messages: list[LlmMessage], response_model: type[ResponseT]
    ) -> ResponseT:
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part(text=message.content)],
            )
            for message in messages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_schema=response_model,
            temperature=0.4,
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model, contents=contents, config=config
            )
        except errors.APIError as error:
            raise LlmUnavailableError(f"{self.name} returned {error.code}") from error
        except Exception as error:  # Timeouts and connection failures from the transport.
            raise LlmUnavailableError(f"{self.name} failed: {type(error).__name__}") from error

        if isinstance(response.parsed, response_model):
            return response.parsed
        try:
            return response_model.model_validate_json(response.text or "")
        except ValidationError as error:
            raise LlmUnavailableError(f"{self.name} returned malformed output") from error
