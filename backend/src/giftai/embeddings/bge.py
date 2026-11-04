"""bge-small-en-v1.5 run locally through fastembed (ONNX on the CPU, no API calls)."""

import threading
from collections.abc import Sequence
from pathlib import Path

import numpy as np
from fastembed import TextEmbedding

from giftai.embeddings.base import EMBEDDING_DIMENSIONS, Matrix, Vector, normalize_rows

# BGE models retrieve better when a short query carries this instruction; documents don't.
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "


class FastEmbedTextEmbedder:
    """Loads the model on first use, so an app that never searches never pays for it."""

    def __init__(
        self, model_name: str, cache_dir: Path | None = None, batch_size: int = 64
    ) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._model: TextEmbedding | None = None
        self._lock = threading.Lock()

    def embed_documents(self, texts: Sequence[str]) -> Matrix:
        if not texts:
            return np.empty((0, EMBEDDING_DIMENSIONS), dtype=np.float32)
        rows = list(self._get_model().embed(list(texts), batch_size=self._batch_size))
        return self._checked(np.asarray(rows, dtype=np.float32))

    def embed_query(self, text: str) -> Vector:
        rows = list(self._get_model().embed([BGE_QUERY_INSTRUCTION + text]))
        vector: Vector = self._checked(np.asarray(rows, dtype=np.float32))[0]
        return vector

    def load(self) -> None:
        """Load the model now instead of on the first request."""
        self._get_model()

    def _get_model(self) -> TextEmbedding:
        with self._lock:
            if self._model is None:
                cache_dir = str(self._cache_dir) if self._cache_dir else None
                self._model = TextEmbedding(self._model_name, cache_dir=cache_dir)
            return self._model

    def _checked(self, matrix: Matrix) -> Matrix:
        if matrix.shape[1] != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"{self._model_name} returned {matrix.shape[1]} dimensions; "
                f"the catalog stores {EMBEDDING_DIMENSIONS}."
            )
        return normalize_rows(matrix)
