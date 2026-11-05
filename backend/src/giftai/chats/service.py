import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from giftai.chats.models import Chat, Message
from giftai.chats.repository import ChatRepository, MessageRepository
from giftai.chats.schemas import ChatCreate, ChatUpdate
from giftai.chats.titles import describe_chat, sentence_case
from giftai.core.errors import InvalidRequestError, LimitReachedError, NotFoundError
from giftai.core.pagination import PageRequest, PageResult
from giftai.recipients.models import Recipient
from giftai.recipients.service import RecipientService
from giftai.users.models import User

# Storage caps that keep one account from filling the free database.
MAX_CHATS_PER_USER = 500
MAX_MESSAGES_PER_CHAT = 400


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._chats = ChatRepository(session)
        self._messages = MessageRepository(session)
        self._recipients = RecipientService(session)

    async def list_page(self, user: User, page: PageRequest) -> PageResult[Chat]:
        return await self._chats.list_owned(user.id, page)

    async def get(self, user: User, chat_id: uuid.UUID) -> Chat:
        chat = await self._chats.get_owned(user.id, chat_id)
        if chat is None:
            raise NotFoundError("We couldn't find that chat.")
        return chat

    async def create(self, user: User, data: ChatCreate) -> Chat:
        if await self._chats.count_owned(user.id) >= MAX_CHATS_PER_USER:
            raise LimitReachedError(
                f"You can keep up to {MAX_CHATS_PER_USER} chats. "
                "Delete an old one to start another."
            )
        recipient = await self._owned_recipient(user, data.recipient_id)
        chat = Chat(
            user_id=user.id,
            title_is_custom=data.title is not None,
            **data.model_dump(exclude={"title"}),
        )
        chat.title = (
            sentence_case(data.title) if data.title else self._automatic_title(chat, recipient)
        )
        self._chats.add(chat)
        await self._session.commit()
        await self._session.refresh(chat)
        return chat

    async def update(self, user: User, chat_id: uuid.UUID, data: ChatUpdate) -> Chat:
        chat = await self.get(user, chat_id)
        changes = data.changes()

        if "title" in changes:
            new_title = changes.pop("title")
            chat.title_is_custom = new_title is not None
            if new_title is not None:
                chat.title = sentence_case(new_title)
        for field, value in changes.items():
            setattr(chat, field, value)

        if (
            chat.budget_min_usd is not None
            and chat.budget_max_usd is not None
            and chat.budget_min_usd > chat.budget_max_usd
        ):
            raise InvalidRequestError("The minimum budget can't be more than the maximum.")

        recipient = await self._owned_recipient(user, chat.recipient_id)
        if not chat.title_is_custom:
            chat.title = self._automatic_title(chat, recipient)

        await self._session.commit()
        await self._session.refresh(chat)
        return chat

    async def delete(self, user: User, chat_id: uuid.UUID) -> None:
        chat = await self.get(user, chat_id)
        await self._chats.delete(chat)
        await self._session.commit()

    async def list_messages(
        self, user: User, chat_id: uuid.UUID, page: PageRequest
    ) -> PageResult[Message]:
        chat = await self.get(user, chat_id)
        return await self._messages.list_for_chat(chat.id, page)

    async def _owned_recipient(
        self, user: User, recipient_id: uuid.UUID | None
    ) -> Recipient | None:
        if recipient_id is None:
            return None
        return await self._recipients.get(user, recipient_id)

    @staticmethod
    def _automatic_title(chat: Chat, recipient: Recipient | None) -> str:
        return describe_chat(
            recipient.name if recipient else None, chat.occasion, chat.occasion_date
        )
