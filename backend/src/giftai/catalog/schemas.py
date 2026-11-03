from decimal import Decimal
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    computed_field,
    model_validator,
)

from giftai.catalog import links
from giftai.core.validation import BudgetDollars

# What a search box needs; long enough for "gift for a coffee lover who hikes".
SearchText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
# Amazon's 10-character product id, such as B07XYZ1234 or a 10-digit ISBN.
Asin = Annotated[str, StringConstraints(pattern=r"^[A-Z0-9]{10}$")]

MAX_SEARCH_RESULTS = 50
MAX_NEIGHBORS = 50


class ProductSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: SearchText
    limit: int = Field(default=20, ge=1, le=MAX_SEARCH_RESULTS)
    min_price: BudgetDollars | None = None
    max_price: BudgetDollars | None = None

    @model_validator(mode="after")
    def _check_price_range(self) -> Self:
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price can't be more than max_price")
        return self


class NeighborsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=10, ge=1, le=MAX_NEIGHBORS)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asin: str
    title: str
    brand: str | None
    main_category: str
    category_path: list[str]
    price_2023: Decimal
    rating_average: float
    rating_count: int
    image_url: str
    short_description: str | None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amazon_url(self) -> str:
        return links.product_url(self.asin)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def amazon_search_url(self) -> str:
        """A fallback for when the listing has gone: search Amazon for the same name."""
        return links.search_url(self.title)


class ScoredProduct(BaseModel):
    product: ProductRead
    # Search: cosine similarity of meaning, -1 to 1. Neighbors: ALS similarity.
    score: float


class ScoredProducts(BaseModel):
    items: list[ScoredProduct]
