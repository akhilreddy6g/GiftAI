from typing import Annotated

from fastapi import Depends

from giftai.catalog.service import ProductCatalogService
from giftai.db.session import SessionDep
from giftai.embeddings.dependencies import TextEmbedderDep


def get_product_catalog_service(
    session: SessionDep, embedder: TextEmbedderDep
) -> ProductCatalogService:
    return ProductCatalogService(session, embedder)


ProductCatalogServiceDep = Annotated[ProductCatalogService, Depends(get_product_catalog_service)]
