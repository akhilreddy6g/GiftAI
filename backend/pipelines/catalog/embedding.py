"""Embeds every selected product with the same model the API uses for search queries."""

import logging
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from giftai.catalog.text import product_document
from giftai.embeddings.base import EMBEDDING_DIMENSIONS, TextEmbedder
from pipelines.catalog.records import CatalogProduct

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024


@dataclass(frozen=True)
class ProductEmbeddings:
    asins: npt.NDArray[np.str_]
    # Half precision, as the database stores them.
    vectors: npt.NDArray[np.float16]

    def __post_init__(self) -> None:
        if self.vectors.shape != (len(self.asins), EMBEDDING_DIMENSIONS):
            raise ValueError(f"Expected {len(self.asins)} x {EMBEDDING_DIMENSIONS} vectors")

    def by_asin(self) -> dict[str, npt.NDArray[np.float16]]:
        return dict(zip(self.asins.tolist(), self.vectors, strict=True))


def embed_products(products: Sequence[CatalogProduct], embedder: TextEmbedder) -> ProductEmbeddings:
    documents = [
        product_document(product.title, product.brand, product.category_path, product.features)
        for product in products
    ]
    chunks: list[npt.NDArray[np.float16]] = []
    for start in range(0, len(documents), _CHUNK_SIZE):
        chunk = embedder.embed_documents(documents[start : start + _CHUNK_SIZE])
        chunks.append(chunk.astype(np.float16))
        logger.info(
            "Embedded %d of %d products", min(start + _CHUNK_SIZE, len(documents)), len(documents)
        )
    vectors = (
        np.concatenate(chunks) if chunks else np.empty((0, EMBEDDING_DIMENSIONS), dtype=np.float16)
    )
    asins = np.array([product.asin for product in products], dtype="<U10")
    return ProductEmbeddings(asins, vectors)
