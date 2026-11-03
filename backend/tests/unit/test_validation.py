import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from giftai.core.errors import InvalidRequestError
from giftai.core.pagination import Cursor
from giftai.gifting import Relationship
from giftai.recipients.schemas import RecipientCreate, RecipientUpdate


def test_interests_are_trimmed_and_deduplicated_ignoring_case() -> None:
    recipient = RecipientCreate(
        name="  Mom ",
        relationship=Relationship.PARENT,
        interests=["Gardening", " gardening ", "Jazz"],
    )

    assert recipient.name == "Mom"
    assert recipient.interests == ["Gardening", "Jazz"]


def test_overlong_text_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RecipientCreate(name="x" * 81, relationship=Relationship.FRIEND)


def test_partial_updates_report_only_the_fields_sent() -> None:
    update = RecipientUpdate.model_validate({"notes": None})

    assert update.changes() == {"notes": None}


def test_partial_updates_cannot_null_required_fields() -> None:
    with pytest.raises(ValidationError, match="name can't be empty"):
        RecipientUpdate.model_validate({"name": None})


def test_cursors_round_trip() -> None:
    cursor = Cursor(datetime(2026, 11, 3, 6, 0, 0, 123456, tzinfo=UTC), uuid.uuid4())

    assert Cursor.decode(cursor.encode()) == cursor


@pytest.mark.parametrize("token", ["", "not-base64!", "WzFd"])
def test_tampered_cursors_are_a_client_error(token: str) -> None:
    with pytest.raises(InvalidRequestError):
        Cursor.decode(token)
