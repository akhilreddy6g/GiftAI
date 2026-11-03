"""Cursor pagination shared by every list endpoint.

Lists are ordered newest first by a timestamp, with the row id as a tie-breaker. The
cursor is an opaque token encoding the last row's (timestamp, id), so a page stays correct
even while rows are being added, and no query ever scans skipped rows the way OFFSET does.
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel

from giftai.core.errors import InvalidRequestError

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 50


@dataclass(frozen=True)
class PageResult[RowT]:
    """One page of rows as the data layer returns them."""

    rows: list[RowT]
    next_cursor: str | None


class Page[ItemT: BaseModel](BaseModel):
    """One page of items as the API returns them."""

    items: list[ItemT]
    # Pass back as ``cursor`` to get the next page; null when there are no more items.
    next_cursor: str | None

    @classmethod
    def of(cls, result: PageResult[Any], item_schema: type[ItemT]) -> "Page[ItemT]":
        return cls(
            items=[item_schema.model_validate(row) for row in result.rows],
            next_cursor=result.next_cursor,
        )


@dataclass(frozen=True)
class Cursor:
    sort_value: datetime
    row_id: uuid.UUID

    def encode(self) -> str:
        payload = json.dumps([self.sort_value.isoformat(), str(self.row_id)])
        return base64.urlsafe_b64encode(payload.encode()).decode()

    @classmethod
    def decode(cls, token: str) -> "Cursor":
        try:
            sort_value, row_id = json.loads(base64.urlsafe_b64decode(token.encode()))
            return cls(datetime.fromisoformat(sort_value), uuid.UUID(row_id))
        except (binascii.Error, json.JSONDecodeError, TypeError, ValueError) as error:
            raise InvalidRequestError("That page link is no longer valid.") from error


@dataclass(frozen=True)
class PageRequest:
    limit: int
    cursor: Cursor | None


def get_page_request(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> PageRequest:
    return PageRequest(limit=limit, cursor=Cursor.decode(cursor) if cursor else None)


PageRequestDep = Annotated[PageRequest, Depends(get_page_request)]
