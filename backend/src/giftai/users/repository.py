import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID) -> User | None:
        return await self._session.get(User, user_id)

    def add(self, user: User) -> None:
        self._session.add(user)

    async def delete(self, user_id: uuid.UUID) -> None:
        # Recipients, chats and messages go with it through ON DELETE CASCADE.
        await self._session.execute(delete(User).where(User.id == user_id))
