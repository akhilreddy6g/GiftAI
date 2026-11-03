"""Links into amazon.com. GiftAI never touches the user's Amazon account; it only links."""

from urllib.parse import quote_plus

AMAZON_BASE_URL = "https://www.amazon.com"
_SEARCH_TERMS_MAX_LENGTH = 100


def product_url(asin: str) -> str:
    return f"{AMAZON_BASE_URL}/dp/{asin}"


def search_url(title: str) -> str:
    """A search for the product's name: still useful when the listing itself is gone."""
    return f"{AMAZON_BASE_URL}/s?k={quote_plus(title[:_SEARCH_TERMS_MAX_LENGTH])}"
