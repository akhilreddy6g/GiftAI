"""Links into amazon.com. GiftAI never touches the user's Amazon account; it only links."""

from urllib.parse import quote_plus

AMAZON_BASE_URL = "https://www.amazon.com"
_SEARCH_TERMS_MAX_LENGTH = 100


def product_url(asin: str) -> str:
    return f"{AMAZON_BASE_URL}/dp/{asin}"


def search_url(title: str) -> str:
    """A search for the product's name: still useful when the listing itself is gone."""
    return f"{AMAZON_BASE_URL}/s?k={quote_plus(title[:_SEARCH_TERMS_MAX_LENGTH])}"


def add_to_cart_url(asins: list[str]) -> str:
    """Amazon's add-to-cart link: Amazon asks the signed-in user to confirm adding these
    items to their own cart. GiftAI never sees the cart or the account.
    """
    params = "&".join(
        f"ASIN.{number}={asin}&Quantity.{number}=1" for number, asin in enumerate(asins, 1)
    )
    return f"{AMAZON_BASE_URL}/gp/aws/cart/add.html?{params}"
