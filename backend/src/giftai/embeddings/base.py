"""The text-embedding interface the rest of the app depends on.

An embedder turns text into unit-length vectors, so that cosine similarity between two
vectors measures how close two texts are in meaning. Products are embedded offline as
documents; what a user is looking for is embedded at request time as a query. Both must
come from the same model, or the numbers can't be compared.
"""

from collections.abc import Sequence
from typing import Protocol

import numpy as np
import numpy.typing as npt

# bge-small-en-v1.5 produces 384 numbers per text; the database column has this size.
EMBEDDING_DIMENSIONS = 384

Vector = npt.NDArray[np.float32]
Matrix = npt.NDArray[np.float32]


class TextEmbedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        """One unit-length row per text, in the same order."""
        ...

    def embed_query(self, text: str) -> Vector:
        """A unit-length vector for a short search phrase."""
        ...


def normalize_rows(matrix: Matrix) -> Matrix:
    """Scale each row to length 1 (rows of zeros stay zero), so dot product is cosine."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms > 0)
