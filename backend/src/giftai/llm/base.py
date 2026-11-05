"""The LLM interface the agent depends on, so providers can be swapped or stacked.

Every call returns a Pydantic model: the agent only ever consumes structured output,
which is validated before any of it is used.
"""

from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar

from pydantic import BaseModel

ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True)
class LlmMessage:
    role: Literal["user", "assistant"]
    content: str


class LlmUnavailableError(Exception):
    """The provider is overloaded, rate limited, unreachable or returned nothing usable.
    Worth trying another provider; never shown to users as is.
    """


class ChatModel(Protocol):
    @property
    def name(self) -> str: ...

    async def generate(
        self,
        system: str,
        messages: list[LlmMessage],
        response_model: type[ResponseT],
    ) -> ResponseT: ...
