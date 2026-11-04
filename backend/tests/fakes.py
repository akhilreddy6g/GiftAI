"""Stand-ins for heavy dependencies, so tests run without downloading models."""

import hashlib
import re
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from giftai.embeddings.base import EMBEDDING_DIMENSIONS, Matrix, Vector, normalize_rows
from giftai.llm.base import LlmMessage, LlmUnavailableError, ResponseT

_WORD = re.compile(r"[a-z]+")


class HashingTextEmbedder:
    """A bag-of-words embedder: texts sharing words get similar vectors.

    Crude, but it behaves like a real embedder where tests care: "coffee" finds the
    coffee products, and every vector has unit length.
    """

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        matrix = np.zeros((len(texts), EMBEDDING_DIMENSIONS), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in _WORD.findall(text.lower()):
                digest = hashlib.blake2b(word.encode(), digest_size=4).digest()
                matrix[row, int.from_bytes(digest) % EMBEDDING_DIMENSIONS] += 1.0
        return normalize_rows(matrix)

    def embed_query(self, text: str) -> Vector:
        vector: Vector = self.embed_documents([text])[0]
        return vector


class ScriptedChatModel:
    """An LLM stand-in that answers each request type from a script.

    ``answers`` maps a response model to a function of (system prompt, conversation)
    that returns an instance of it, so tests decide exactly what the "LLM" says.
    """

    name = "scripted"

    def __init__(self, answers: dict[type[Any], Callable[[str, list[LlmMessage]], Any]]) -> None:
        self.answers = answers
        self.calls: list[tuple[type[Any], str, list[LlmMessage]]] = []
        self.unavailable = False

    async def generate(
        self, system: str, messages: list[LlmMessage], response_model: type[ResponseT]
    ) -> ResponseT:
        self.calls.append((response_model, system, list(messages)))
        if self.unavailable:
            raise LlmUnavailableError("scripted outage")
        answer = self.answers[response_model](system, messages)
        assert isinstance(answer, response_model)
        return answer
