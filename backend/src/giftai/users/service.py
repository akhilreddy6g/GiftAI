from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.auth.tokens import AuthenticatedPrincipal
from giftai.users.models import User
from giftai.users.repository import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def ensure_account(self, principal: AuthenticatedPrincipal) -> User:
        """Return the caller's active account, creating one if they have none.

        Accounts are created lazily because sign-up happens in Supabase, which doesn't
        notify us; the first authenticated request is the first moment we hear of a user.
        After a deletion, the next request starts a fresh account.
        """
        user = await self._users.get_active_by_auth_user_id(principal.user_id)
        if user is None:
            return await self._create(principal)
        if principal.email and user.email != principal.email:
            user.email = principal.email
            await self._session.commit()
        return user

    async def delete_account(self, user: User) -> None:
        """Flag the account deleted. Its data is kept but never served again.

        A purge job can hard-delete flagged accounts later: the foreign keys already
        cascade from users to recipients, chats and messages.
        """
        user.deleted_at = datetime.now(UTC)
        await self._session.commit()

    async def _create(self, principal: AuthenticatedPrincipal) -> User:
        user = User(auth_user_id=principal.user_id, email=principal.email)
        self._users.add(user)
        try:
            await self._session.commit()
        except IntegrityError:
            # Two first requests raced; the other one created the account.
            await self._session.rollback()
            existing = await self._users.get_active_by_auth_user_id(principal.user_id)
            if existing is None:
                raise
            return existing
        await self._session.refresh(user)
        return user
