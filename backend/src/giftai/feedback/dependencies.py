from typing import Annotated

from fastapi import Depends

from giftai.db.session import SessionDep
from giftai.feedback.service import FeedbackService


def get_feedback_service(session: SessionDep) -> FeedbackService:
    return FeedbackService(session)


FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]
