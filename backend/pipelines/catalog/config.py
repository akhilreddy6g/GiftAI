"""What makes the catalog: which dataset categories, how many products each, and the rules
a product must pass to be worth recommending as a gift.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

# Products per dataset category, about 85,000 in total: enough variety while the
# catalog, its vectors and their index stay well inside the free 1 GB database.
CATEGORY_QUOTAS: dict[str, int] = {
    "Home_and_Kitchen": 18_000,
    "Toys_and_Games": 9_000,
    "Sports_and_Outdoors": 8_000,
    "Beauty_and_Personal_Care": 8_000,
    "Electronics": 7_000,
    "Books": 6_000,
    "Clothing_Shoes_and_Jewelry": 6_000,
    "Arts_Crafts_and_Sewing": 5_000,
    "Grocery_and_Gourmet_Food": 5_000,
    "Office_Products": 3_000,
    "Pet_Supplies": 3_000,
    "Video_Games": 2_000,
    "Musical_Instruments": 2_000,
    "Baby_Products": 2_000,
    "Patio_Lawn_and_Garden": 2_000,
}
# For a category passed on the command line that isn't listed above.
DEFAULT_CATEGORY_QUOTA = 5_000


@dataclass(frozen=True)
class SelectionRules:
    # Enough reviews that the rating means something and the product is established.
    min_rating_count: int = 50
    min_rating_average: float = 3.8
    # A gift budget range; outside it are stocking-filler scraps and big-ticket items.
    min_price: Decimal = Decimal(5)
    max_price: Decimal = Decimal(500)
    # Reviewed in the dataset's last year: the likeliest to still be on sale.
    reviewed_since: date = date(2022, 9, 1)
    # Breadcrumb words that mark things nobody wants as a gift.
    excluded_category_terms: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "replacement",
                "industrial",
                "batteries",
                "cables",
                "adapters",
                "screen protectors",
                "medical supplies",
                "incontinence",
                "feminine care",
            }
        )
    )


def quota_for(category: str, scale: float = 1.0) -> int:
    return max(1, round(CATEGORY_QUOTAS.get(category, DEFAULT_CATEGORY_QUOTA) * scale))
