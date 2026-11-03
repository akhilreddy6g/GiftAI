from fastapi import APIRouter, status

from giftai.auth.dependencies import CurrentUser
from giftai.users.dependencies import UserServiceDep
from giftai.users.schemas import UserRead

router = APIRouter(prefix="/me", tags=["account"])


@router.get("", summary="The signed-in user's account")
async def get_my_account(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete the account; signing in again starts a fresh, empty one",
)
async def delete_my_account(user: CurrentUser, service: UserServiceDep) -> None:
    await service.delete_account(user)
