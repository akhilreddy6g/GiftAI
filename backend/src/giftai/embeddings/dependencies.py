from typing import Annotated

from fastapi import Depends, Request

from giftai.core.config import EmbeddingSettings
from giftai.embeddings.base import TextEmbedder
from giftai.embeddings.bge import FastEmbedTextEmbedder


def build_text_embedder(settings: EmbeddingSettings) -> FastEmbedTextEmbedder:
    return FastEmbedTextEmbedder(settings.embedding_model_name, settings.embedding_cache_dir)


def get_text_embedder(request: Request) -> TextEmbedder:
    embedder: TextEmbedder = request.app.state.text_embedder
    return embedder


TextEmbedderDep = Annotated[TextEmbedder, Depends(get_text_embedder)]
