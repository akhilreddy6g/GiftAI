import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.chats.models import Chat, Message
from giftai.core.pagination import PageRequest, PageResult
from giftai.db.pagination import fetch_page


class ChatRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owned(self, user_id: uuid.UUID, chat_id: uuid.UUID) -> Chat | None:
        """The chat, only if it belongs to ``user_id``."""
        return await self._session.scalar(
            select(Chat).where(Chat.id == chat_id, Chat.user_id == user_id)
        )

    async def list_owned(self, user_id: uuid.UUID, page: PageRequest) -> PageResult[Chat]:
        return await fetch_page(
            self._session,
            select(Chat).where(Chat.user_id == user_id),
            page,
            sort_column=Chat.updated_at,
            id_column=Chat.id,
        )

    async def count_owned(self, user_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(Chat).where(Chat.user_id == user_id)
        )
        return count or 0

    def add(self, chat: Chat) -> None:
        self._session.add(chat)

    async def mark_active(self, chat_id: uuid.UUID) -> None:
        """Bump ``updated_at`` so the chat rises to the top of the sidebar."""
        await self._session.execute(
            update(Chat).where(Chat.id == chat_id).values(updated_at=func.now())
        )

    async def delete(self, chat: Chat) -> None:
        await self._session.delete(chat)


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_chat(self, chat_id: uuid.UUID, page: PageRequest) -> PageResult[Message]:
        return await fetch_page(
            self._session,
            select(Message).where(Message.chat_id == chat_id),
            page,
            sort_column=Message.created_at,
            id_column=Message.id,
        )

    async def count_for_chat(self, chat_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count()).select_from(Message).where(Message.chat_id == chat_id)
        )
        return count or 0

    async def recent_for_chat(self, chat_id: uuid.UUID, limit: int) -> list[Message]:
        """The latest messages, oldest first, as the agent reads the conversation."""
        rows = await self._session.scalars(
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit)
        )
        return list(reversed(rows.all()))

    def add(self, message: Message) -> None:
        self._session.add(message)
