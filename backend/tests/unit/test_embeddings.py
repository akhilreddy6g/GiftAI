from collections.abc import Iterator

import numpy as np
import pytest

from giftai.embeddings import bge
from giftai.embeddings.base import EMBEDDING_DIMENSIONS, normalize_rows
from giftai.embeddings.bge import BGE_QUERY_INSTRUCTION, FastEmbedTextEmbedder


class RecordingModel:
    """Stands in for fastembed's TextEmbedding: returns un-normalised vectors."""

    instances: list["RecordingModel"] = []  # noqa: RUF012

    def __init__(self, model_name: str, cache_dir: str | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir
        self.texts: list[str] = []
        RecordingModel.instances.append(self)

    def embed(self, texts: list[str], batch_size: int = 256) -> Iterator[np.ndarray]:
        for text in texts:
            self.texts.append(text)
            yield np.full(EMBEDDING_DIMENSIONS, 3.0, dtype=np.float32)


@pytest.fixture
def embedder(monkeypatch: pytest.MonkeyPatch) -> FastEmbedTextEmbedder:
    RecordingModel.instances.clear()
    monkeypatch.setattr(bge, "TextEmbedding", RecordingModel)
    return FastEmbedTextEmbedder("BAAI/bge-small-en-v1.5")


def test_the_model_loads_once_on_first_use(embedder: FastEmbedTextEmbedder) -> None:
    assert RecordingModel.instances == []

    embedder.embed_query("coffee")
    embedder.embed_documents(["a", "b"])

    assert len(RecordingModel.instances) == 1


def test_queries_carry_the_bge_instruction_and_documents_do_not(
    embedder: FastEmbedTextEmbedder,
) -> None:
    embedder.embed_query("gift for a coffee lover")
    embedder.embed_documents(["Pour-over kit"])

    assert RecordingModel.instances[0].texts == [
        BGE_QUERY_INSTRUCTION + "gift for a coffee lover",
        "Pour-over kit",
    ]


def test_vectors_come_back_unit_length(embedder: FastEmbedTextEmbedder) -> None:
    query = embedder.embed_query("coffee")
    documents = embedder.embed_documents(["a", "b"])

    assert query.shape == (EMBEDDING_DIMENSIONS,)
    assert documents.shape == (2, EMBEDDING_DIMENSIONS)
    np.testing.assert_allclose(np.linalg.norm(documents, axis=1), 1.0, rtol=1e-6)
    assert np.linalg.norm(query) == pytest.approx(1.0)


def test_no_documents_means_no_model_load(embedder: FastEmbedTextEmbedder) -> None:
    assert embedder.embed_documents([]).shape == (0, EMBEDDING_DIMENSIONS)
    assert RecordingModel.instances == []


def test_normalizing_leaves_zero_rows_alone() -> None:
    matrix = np.array([[3.0, 4.0], [0.0, 0.0]], dtype=np.float32)

    np.testing.assert_allclose(normalize_rows(matrix), [[0.6, 0.8], [0.0, 0.0]])
