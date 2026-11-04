from typing import Annotated

from fastapi import Depends, Request

from giftai.core.config import LlmSettings
from giftai.llm.base import ChatModel
from giftai.llm.fallback import FallbackChatModel
from giftai.llm.gemini import GeminiChatModel
from giftai.llm.groq import GroqChatModel


def build_chat_model(settings: LlmSettings) -> ChatModel | None:
    """Gemini first, Groq as the fallback; None when no key is configured, in which case
    the chat still stores messages but the agent answers that it is switched off.
    """
    models: list[ChatModel] = []
    if settings.gemini_api_key is not None:
        models.append(
            GeminiChatModel(
                settings.gemini_api_key.get_secret_value(),
                settings.gemini_model,
                settings.llm_timeout_seconds,
            )
        )
    if settings.groq_api_key is not None:
        models.append(
            GroqChatModel(
                settings.groq_api_key.get_secret_value(),
                settings.groq_model,
                settings.llm_timeout_seconds,
            )
        )
    if not models:
        return None
    return models[0] if len(models) == 1 else FallbackChatModel(models)


def get_chat_model(request: Request) -> ChatModel | None:
    model: ChatModel | None = request.app.state.chat_model
    return model


ChatModelDep = Annotated[ChatModel | None, Depends(get_chat_model)]
