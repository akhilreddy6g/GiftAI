import uuid
from typing import Annotated

from fastapi import APIRouter, Path, status

from giftai.auth.dependencies import CurrentUser
from giftai.catalog.schemas import Asin
from giftai.feedback.dependencies import FeedbackServiceDep
from giftai.feedback.schemas import (
    AvailabilityVoteCreate,
    FeedbackEventCreate,
    ProductAvailability,
    RatingUpdate,
)

router = APIRouter(tags=["feedback"])


@router.post(
    "/feedback/events",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Record that gift ideas were opened on Amazon or added to the cart",
)
async def record_feedback(
    data: FeedbackEventCreate, user: CurrentUser, service: FeedbackServiceDep
) -> None:
    await service.record(user, data)


@router.put(
    "/recommendations/{recommendation_id}/rating",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Thumbs up or down on a gift idea, or null to clear it",
)
async def rate_recommendation(
    recommendation_id: uuid.UUID,
    data: RatingUpdate,
    user: CurrentUser,
    service: FeedbackServiceDep,
) -> None:
    await service.rate(user, recommendation_id, data.rating)


@router.put(
    "/products/{asin}/availability",
    summary="Say whether the product could still be found on Amazon; replaces an earlier vote",
)
async def vote_availability(
    asin: Annotated[Asin, Path(description="Amazon product id (ASIN)")],
    data: AvailabilityVoteCreate,
    user: CurrentUser,
    service: FeedbackServiceDep,
) -> ProductAvailability:
    return await service.vote(user, asin, data.found)
