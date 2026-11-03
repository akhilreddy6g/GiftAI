import uuid

from fastapi import APIRouter, status

from giftai.auth.dependencies import CurrentUser
from giftai.chats.dependencies import ChatServiceDep
from giftai.chats.schemas import ChatCreate, ChatRead, ChatUpdate, MessageCreate, MessageRead
from giftai.core.pagination import Page, PageRequestDep

router = APIRouter(prefix="/chats", tags=["chats"])


@router.get("", summary="The user's chats, most recently active first")
async def list_chats(
    user: CurrentUser, service: ChatServiceDep, page: PageRequestDep
) -> Page[ChatRead]:
    return Page.of(await service.list_page(user, page), ChatRead)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Start a chat")
async def create_chat(data: ChatCreate, user: CurrentUser, service: ChatServiceDep) -> ChatRead:
    return ChatRead.model_validate(await service.create(user, data))


@router.get("/{chat_id}", summary="One chat's details")
async def get_chat(chat_id: uuid.UUID, user: CurrentUser, service: ChatServiceDep) -> ChatRead:
    return ChatRead.model_validate(await service.get(user, chat_id))


@router.patch("/{chat_id}", summary="Change some of a chat's details")
async def update_chat(
    chat_id: uuid.UUID, data: ChatUpdate, user: CurrentUser, service: ChatServiceDep
) -> ChatRead:
    return ChatRead.model_validate(await service.update(user, chat_id, data))


@router.delete(
    "/{chat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a chat and its messages",
)
async def delete_chat(chat_id: uuid.UUID, user: CurrentUser, service: ChatServiceDep) -> None:
    await service.delete(user, chat_id)


@router.get("/{chat_id}/messages", summary="A chat's messages, newest first")
async def list_messages(
    chat_id: uuid.UUID, user: CurrentUser, service: ChatServiceDep, page: PageRequestDep
) -> Page[MessageRead]:
    return Page.of(await service.list_messages(user, chat_id, page), MessageRead)


@router.post(
    "/{chat_id}/messages",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message in a chat",
)
async def send_message(
    chat_id: uuid.UUID, data: MessageCreate, user: CurrentUser, service: ChatServiceDep
) -> MessageRead:
    return MessageRead.model_validate(await service.add_user_message(user, chat_id, data))
