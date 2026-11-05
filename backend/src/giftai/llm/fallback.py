import logging

from giftai.llm.base import ChatModel, LlmMessage, LlmUnavailableError, ResponseT

logger = logging.getLogger(__name__)


class FallbackChatModel:
    """Tries each model in order until one answers."""

    def __init__(self, models: list[ChatModel]) -> None:
        if not models:
            raise ValueError("FallbackChatModel needs at least one model")
        self._models = models

    @property
    def name(self) -> str:
        return " > ".join(model.name for model in self._models)

    async def generate(
        self, system: str, messages: list[LlmMessage], response_model: type[ResponseT]
    ) -> ResponseT:
        failures: list[str] = []
        for model in self._models:
            try:
                return await model.generate(system, messages, response_model)
            except LlmUnavailableError as error:
                logger.warning("LLM %s unavailable: %s", model.name, error)
                failures.append(str(error))
        raise LlmUnavailableError("; ".join(failures))
