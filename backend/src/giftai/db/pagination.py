"""Runs a keyset-paginated query; see ``giftai.core.pagination`` for the scheme."""

import uuid
from datetime import datetime

from sqlalchemy import Select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from giftai.core.pagination import Cursor, PageRequest, PageResult


async def fetch_page[RowT](
    session: AsyncSession,
    statement: Select[RowT],
    page: PageRequest,
    sort_column: InstrumentedAttribute[datetime],
    id_column: InstrumentedAttribute[uuid.UUID],
) -> PageResult[RowT]:
    """Fetch one page of ``statement``'s rows, newest ``sort_column`` first."""
    if page.cursor is not None:
        statement = statement.where(
            tuple_(sort_column, id_column) < tuple_(page.cursor.sort_value, page.cursor.row_id)
        )
    # One extra row tells us whether another page exists without a COUNT query.
    statement = statement.order_by(sort_column.desc(), id_column.desc()).limit(page.limit + 1)
    rows = list((await session.scalars(statement)).all())

    if len(rows) <= page.limit:
        return PageResult(rows=rows, next_cursor=None)
    rows = rows[: page.limit]
    last = rows[-1]
    cursor = Cursor(getattr(last, sort_column.key), getattr(last, id_column.key))
    return PageResult(rows=rows, next_cursor=cursor.encode())
