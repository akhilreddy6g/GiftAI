from typing import Annotated

from fastapi import Depends

from giftai.chats.service import ChatService
from giftai.db.session import SessionDep


def get_chat_service(session: SessionDep) -> ChatService:
    return ChatService(session)


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]
