"""Automatic chat titles, e.g. "Mom, birthday, Dec 14", so the sidebar reads at a glance."""

from datetime import date

from giftai.gifting import Occasion

UNTITLED_CHAT = "New gift idea"


def describe_chat(
    recipient_name: str | None, occasion: Occasion | None, occasion_date: date | None
) -> str:
    parts: list[str] = []
    if recipient_name:
        parts.append(recipient_name)
    if occasion and occasion is not Occasion.OTHER:
        parts.append(occasion.value.replace("_", " "))
    if occasion_date:
        parts.append(f"{occasion_date:%b} {occasion_date.day}")
    return ", ".join(parts) or UNTITLED_CHAT
