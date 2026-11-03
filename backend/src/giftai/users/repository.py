import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.users.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_by_auth_user_id(self, auth_user_id: uuid.UUID) -> User | None:
        """The sign-in's current account; deleted accounts are never returned."""
        return await self._session.scalar(
            select(User).where(User.auth_user_id == auth_user_id, User.deleted_at.is_(None))
        )

    def add(self, user: User) -> None:
        self._session.add(user)
