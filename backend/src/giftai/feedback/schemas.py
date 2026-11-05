import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from giftai.feedback.availability import AvailabilityStatus

Rating = Literal["up", "down"]


class FeedbackEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Ratings have their own endpoint, since they replace each other.
    kind: Literal["clicked", "added_to_cart"]
    # Several at once for "add all to cart"; a reply never has more than a handful of picks.
    recommendation_ids: list[uuid.UUID] = Field(min_length=1, max_length=10)


class RatingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # null clears the rating.
    rating: Rating | None


class AvailabilityVoteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found: bool


class ProductAvailability(BaseModel):
    status: AvailabilityStatus
    found_votes: int
    not_found_votes: int
    # The signed-in user's own vote: true found it, false didn't, null hasn't said.
    your_vote: bool | None
