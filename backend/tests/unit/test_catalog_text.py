from giftai.catalog.links import product_url, search_url
from giftai.catalog.text import product_document


def test_product_document_combines_the_searchable_details() -> None:
    document = product_document(
        "Pour-Over Kit",
        "Hario",
        ["Home & Kitchen", "Coffee"],
        ["Glass carafe", " ", "Paper filters", "4", "5", "6 is too many"],
    )

    assert document == (
        "Pour-Over Kit. Brand: Hario. Category: Home & Kitchen > Coffee. "
        "Glass carafe. Paper filters. 4. 5"
    )


def test_product_document_skips_what_is_missing() -> None:
    assert product_document("Yoga Mat", None, [], []) == "Yoga Mat"


def test_amazon_links() -> None:
    assert product_url("B07XYZ1234") == "https://www.amazon.com/dp/B07XYZ1234"
    assert search_url("Mug & Tea Set") == "https://www.amazon.com/s?k=Mug+%26+Tea+Set"
