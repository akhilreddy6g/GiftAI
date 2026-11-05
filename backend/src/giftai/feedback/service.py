import uuid
from collections.abc import Collection

from sqlalchemy.ext.asyncio import AsyncSession

from giftai.catalog.repository import ProductRepository
from giftai.core.errors import NotFoundError
from giftai.feedback.availability import VoteCounts
from giftai.feedback.models import FeedbackEvent, FeedbackKind
from giftai.feedback.repository import AvailabilityRepository, FeedbackRepository
from giftai.feedback.schemas import FeedbackEventCreate, ProductAvailability, Rating
from giftai.users.models import User

RATING_VALUES: dict[Rating, int] = {"up": 1, "down": -1}
RATING_EVENTS: dict[Rating | None, FeedbackKind] = {
    "up": FeedbackKind.THUMBS_UP,
    "down": FeedbackKind.THUMBS_DOWN,
    None: FeedbackKind.RATING_CLEARED,
}


def rating_name(value: int | None) -> Rating | None:
    """The stored rating (1, -1 or null) as the API names it."""
    if value == 1:
        return "up"
    if value == -1:
        return "down"
    return None


class FeedbackService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._feedback = FeedbackRepository(session)
        self._availability = AvailabilityRepository(session)
        self._products = ProductRepository(session)

    async def record(self, user: User, data: FeedbackEventCreate) -> None:
        ids = set(data.recommendation_ids)
        owned = await self._feedback.owned_recommendations(user.id, ids)
        # All or nothing, and the same answer for someone else's ids as for made-up ones.
        if len(owned) != len(ids):
            raise NotFoundError("We couldn't find those gift ideas.")
        kind = FeedbackKind(data.kind)
        for recommendation in owned:
            self._feedback.add(
                FeedbackEvent(user_id=user.id, recommendation_id=recommendation.id, kind=kind)
            )
        await self._session.commit()

    async def rate(self, user: User, recommendation_id: uuid.UUID, rating: Rating | None) -> None:
        owned = await self._feedback.owned_recommendations(user.id, [recommendation_id])
        if not owned:
            raise NotFoundError("We couldn't find that gift idea.")
        recommendation = owned[0]
        value = RATING_VALUES[rating] if rating is not None else None
        if recommendation.rating != value:
            recommendation.rating = value
            self._feedback.add(
                FeedbackEvent(
                    user_id=user.id,
                    recommendation_id=recommendation.id,
                    kind=RATING_EVENTS[rating],
                )
            )
        await self._session.commit()

    async def vote(self, user: User, asin: str, found: bool) -> ProductAvailability:
        if await self._products.get(asin) is None:
            raise NotFoundError("We couldn't find that product.")
        await self._availability.vote(user.id, asin, found)
        await self._session.commit()
        return (await self.availability(user, [asin]))[asin]

    async def availability(
        self, user: User, asins: Collection[str]
    ) -> dict[str, ProductAvailability]:
        """Each product's status from everyone's votes, with this user's own vote."""
        counts = await self._availability.counts(asins)
        mine = await self._availability.votes_by(user.id, asins)
        result: dict[str, ProductAvailability] = {}
        for asin in asins:
            total = counts.get(asin, VoteCounts())
            result[asin] = ProductAvailability(
                status=total.status,
                found_votes=total.found,
                not_found_votes=total.not_found,
                your_vote=mine.get(asin),
            )
        return result
