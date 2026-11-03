import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from giftai.core.errors import LimitReachedError, NotFoundError
from giftai.core.pagination import PageRequest, PageResult
from giftai.recipients.models import Recipient
from giftai.recipients.repository import RecipientRepository
from giftai.recipients.schemas import RecipientCreate, RecipientUpdate
from giftai.users.models import User

# Keeps one account from filling the free database; far above what a person needs.
MAX_RECIPIENTS_PER_USER = 200


class RecipientService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._recipients = RecipientRepository(session)

    async def list_page(self, user: User, page: PageRequest) -> PageResult[Recipient]:
        return await self._recipients.list_owned(user.id, page)

    async def get(self, user: User, recipient_id: uuid.UUID) -> Recipient:
        recipient = await self._recipients.get_owned(user.id, recipient_id)
        if recipient is None:
            # Same answer whether it doesn't exist or isn't theirs: ids don't leak.
            raise NotFoundError("We couldn't find that person.")
        return recipient

    async def create(self, user: User, data: RecipientCreate) -> Recipient:
        if await self._recipients.count_owned(user.id) >= MAX_RECIPIENTS_PER_USER:
            raise LimitReachedError(
                f"You can save up to {MAX_RECIPIENTS_PER_USER} people. "
                "Remove someone to add another."
            )
        recipient = Recipient(user_id=user.id, **data.model_dump())
        self._recipients.add(recipient)
        await self._session.commit()
        await self._session.refresh(recipient)
        return recipient

    async def update(self, user: User, recipient_id: uuid.UUID, data: RecipientUpdate) -> Recipient:
        recipient = await self.get(user, recipient_id)
        for field, value in data.changes().items():
            setattr(recipient, field, value)
        await self._session.commit()
        await self._session.refresh(recipient)
        return recipient

    async def delete(self, user: User, recipient_id: uuid.UUID) -> None:
        """Delete the person and, with them, every chat about them."""
        recipient = await self.get(user, recipient_id)
        await self._recipients.delete(recipient)
        await self._session.commit()
