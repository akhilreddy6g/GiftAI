"""Stand-ins for heavy dependencies, so tests run without downloading models."""

import hashlib
import re
from collections.abc import Sequence

import numpy as np

from giftai.embeddings.base import EMBEDDING_DIMENSIONS, Matrix, Vector, normalize_rows

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
