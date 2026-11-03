from typing import Annotated

from fastapi import APIRouter, Path, Query

from giftai.catalog.dependencies import ProductCatalogServiceDep
from giftai.catalog.models import Product
from giftai.catalog.schemas import (
    Asin,
    NeighborsQuery,
    ProductRead,
    ProductSearchQuery,
    ScoredProduct,
    ScoredProducts,
)

router = APIRouter(prefix="/products", tags=["products"])

AsinPath = Annotated[Asin, Path(description="Amazon product id (ASIN)")]


@router.get("/search", summary="Products closest in meaning to a phrase")
async def search_products(
    query: Annotated[ProductSearchQuery, Query()], service: ProductCatalogServiceDep
) -> ScoredProducts:
    return _scored(await service.search(query))


@router.get("/{asin}", summary="One product")
async def get_product(asin: AsinPath, service: ProductCatalogServiceDep) -> ProductRead:
    return ProductRead.model_validate(await service.get(asin))


@router.get("/{asin}/also-liked", summary="Products liked by the same people")
async def get_also_liked(
    asin: AsinPath,
    query: Annotated[NeighborsQuery, Query()],
    service: ProductCatalogServiceDep,
) -> ScoredProducts:
    return _scored(await service.also_liked(asin, query))


def _scored(results: list[tuple[Product, float]]) -> ScoredProducts:
    return ScoredProducts(
        items=[
            ScoredProduct(product=ProductRead.model_validate(product), score=round(score, 4))
            for product, score in results
        ]
    )
