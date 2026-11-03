from typing import Annotated

from fastapi import Depends

from giftai.db.session import SessionDep
from giftai.recipients.service import RecipientService


def get_recipient_service(session: SessionDep) -> RecipientService:
    return RecipientService(session)


RecipientServiceDep = Annotated[RecipientService, Depends(get_recipient_service)]
