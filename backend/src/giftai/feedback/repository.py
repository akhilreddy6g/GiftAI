import uuid
from collections.abc import Collection

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.agent.models import Recommendation
from giftai.chats.models import Chat
from giftai.feedback.availability import VoteCounts
from giftai.feedback.models import AvailabilityVote, FeedbackEvent


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def owned_recommendations(
        self, user_id: uuid.UUID, ids: Collection[uuid.UUID]
    ) -> list[Recommendation]:
        """The recommendations among ``ids`` shown in this user's own chats."""
        rows = await self._session.scalars(
            select(Recommendation)
            .join(Chat, Chat.id == Recommendation.chat_id)
            .where(Chat.user_id == user_id, Recommendation.id.in_(ids))
        )
        return list(rows.all())

    def add(self, event: FeedbackEvent) -> None:
        self._session.add(event)


class AvailabilityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def counts(self, asins: Collection[str]) -> dict[str, VoteCounts]:
        """Vote totals per product; products nobody voted on are left out."""
        if not asins:
            return {}
        rows = await self._session.execute(
            select(
                AvailabilityVote.product_asin,
                func.count().filter(AvailabilityVote.found),
                func.count().filter(~AvailabilityVote.found),
            )
            .where(AvailabilityVote.product_asin.in_(asins))
            .group_by(AvailabilityVote.product_asin)
        )
        return {asin: VoteCounts(found, not_found) for asin, found, not_found in rows.all()}

    async def votes_by(self, user_id: uuid.UUID, asins: Collection[str]) -> dict[str, bool]:
        if not asins:
            return {}
        rows = await self._session.execute(
            select(AvailabilityVote.product_asin, AvailabilityVote.found).where(
                AvailabilityVote.user_id == user_id, AvailabilityVote.product_asin.in_(asins)
            )
        )
        return dict(rows.all())

    async def vote(self, user_id: uuid.UUID, asin: str, found: bool) -> None:
        statement = insert(AvailabilityVote).values(user_id=user_id, product_asin=asin, found=found)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[AvailabilityVote.user_id, AvailabilityVote.product_asin],
                set_={"found": found, "updated_at": func.now()},
            )
        )
