import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.core.pagination import PageRequest, PageResult
from giftai.db.pagination import fetch_page
from giftai.recipients.models import Recipient


class RecipientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owned(self, user_id: uuid.UUID, recipient_id: uuid.UUID) -> Recipient | None:
        """The recipient, only if it belongs to ``user_id``."""
        return await self._session.scalar(
            select(Recipient).where(Recipient.id == recipient_id, Recipient.user_id == user_id)
        )

    async def list_owned(self, user_id: uuid.UUID, page: PageRequest) -> PageResult[Recipient]:
        return await fetch_page(
            self._session,
            select(Recipient).where(Recipient.user_id == user_id),
            page,
            sort_column=Recipient.updated_at,
            id_column=Recipient.id,
        )

    async def count_owned(self, user_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(Recipient).where(Recipient.user_id == user_id)
        )
        return count or 0

    def add(self, recipient: Recipient) -> None:
        self._session.add(recipient)

    async def delete(self, recipient: Recipient) -> None:
        await self._session.delete(recipient)
