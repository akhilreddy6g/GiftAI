from typing import Annotated

from fastapi import Depends

from giftai.db.session import SessionDep
from giftai.users.service import UserService


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session)


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
