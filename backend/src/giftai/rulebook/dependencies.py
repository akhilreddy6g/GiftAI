from typing import Annotated

from fastapi import Depends

from giftai.db.session import SessionDep
from giftai.rulebook.service import RulebookService


def get_rulebook_service(session: SessionDep) -> RulebookService:
    return RulebookService(session)


RulebookServiceDep = Annotated[RulebookService, Depends(get_rulebook_service)]
