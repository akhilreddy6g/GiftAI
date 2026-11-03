import uuid

from fastapi import APIRouter, status

from giftai.auth.dependencies import CurrentUser
from giftai.core.pagination import Page, PageRequestDep
from giftai.recipients.dependencies import RecipientServiceDep
from giftai.recipients.schemas import RecipientCreate, RecipientRead, RecipientUpdate

router = APIRouter(prefix="/recipients", tags=["recipients"])


@router.get("", summary="People the user shops for, most recently changed first")
async def list_recipients(
    user: CurrentUser, service: RecipientServiceDep, page: PageRequestDep
) -> Page[RecipientRead]:
    return Page.of(await service.list_page(user, page), RecipientRead)


@router.post("", status_code=status.HTTP_201_CREATED, summary="Save a person")
async def create_recipient(
    data: RecipientCreate, user: CurrentUser, service: RecipientServiceDep
) -> RecipientRead:
    return RecipientRead.model_validate(await service.create(user, data))


@router.get("/{recipient_id}", summary="One saved person")
async def get_recipient(
    recipient_id: uuid.UUID, user: CurrentUser, service: RecipientServiceDep
) -> RecipientRead:
    return RecipientRead.model_validate(await service.get(user, recipient_id))


@router.patch("/{recipient_id}", summary="Change some of a person's details")
async def update_recipient(
    recipient_id: uuid.UUID,
    data: RecipientUpdate,
    user: CurrentUser,
    service: RecipientServiceDep,
) -> RecipientRead:
    return RecipientRead.model_validate(await service.update(user, recipient_id, data))


@router.delete(
    "/{recipient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a person and every chat about them",
)
async def delete_recipient(
    recipient_id: uuid.UUID, user: CurrentUser, service: RecipientServiceDep
) -> None:
    await service.delete(user, recipient_id)
