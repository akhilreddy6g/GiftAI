from datetime import date

from giftai.chats.titles import UNTITLED_CHAT, describe_chat, sentence_case
from giftai.gifting import Occasion


def test_title_combines_person_occasion_and_date() -> None:
    title = describe_chat("Mom", Occasion.BIRTHDAY, date(2026, 12, 4))

    assert title == "Mom, birthday, Dec 4"


def test_title_uses_readable_occasion_names() -> None:
    assert describe_chat("Sam", Occasion.THANK_YOU, None) == "Sam, thank you"


def test_title_skips_the_catch_all_occasion() -> None:
    assert describe_chat("Sam", Occasion.OTHER, None) == "Sam"


def test_an_empty_chat_gets_a_friendly_placeholder() -> None:
    assert describe_chat(None, None, None) == UNTITLED_CHAT


def test_titles_are_sentence_case() -> None:
    assert describe_chat("mom", Occasion.BIRTHDAY, None) == "Mom, birthday"
    assert describe_chat(None, Occasion.BIRTHDAY, date(2026, 12, 4)) == "Birthday, Dec 4"


def test_sentence_case_keeps_the_rest_of_the_title() -> None:
    assert sentence_case("gifts for my iPad-loving dad") == "Gifts for my iPad-loving dad"
    assert sentence_case("") == ""
