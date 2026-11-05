import uuid
from collections.abc import Collection
from datetime import date

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.agent.models import AgentUsage, Recommendation


class RecommendationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def add(self, recommendation: Recommendation) -> None:
        self._session.add(recommendation)

    async def shown_in_chat(self, chat_id: uuid.UUID) -> set[str]:
        rows = await self._session.scalars(
            select(Recommendation.product_asin).where(Recommendation.chat_id == chat_id)
        )
        return set(rows.all())

    async def for_messages(
        self, chat_id: uuid.UUID, message_ids: Collection[uuid.UUID]
    ) -> list[Recommendation]:
        """The picks presented by these replies in this chat, oldest reply first."""
        rows = await self._session.scalars(
            select(Recommendation)
            .where(Recommendation.chat_id == chat_id, Recommendation.message_id.in_(message_ids))
            .order_by(Recommendation.created_at, Recommendation.message_id, Recommendation.rank)
        )
        return list(rows.all())

    async def latest_for_chat(self, chat_id: uuid.UUID) -> list[Recommendation]:
        """The picks from the chat's most recent suggestion reply, best first."""
        latest = (
            select(Recommendation.message_id)
            .where(Recommendation.chat_id == chat_id)
            .order_by(Recommendation.created_at.desc())
            .limit(1)
            .scalar_subquery()
        )
        rows = await self._session.scalars(
            select(Recommendation)
            .where(Recommendation.message_id == latest)
            .order_by(Recommendation.rank)
        )
        return list(rows.all())


class AgentUsageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def turns_on(self, user_id: uuid.UUID, day: date) -> int:
        turns = await self._session.scalar(
            select(AgentUsage.turns).where(AgentUsage.user_id == user_id, AgentUsage.day == day)
        )
        return turns or 0

    async def record_turn(self, user_id: uuid.UUID, day: date) -> None:
        statement = insert(AgentUsage).values(user_id=user_id, day=day, turns=1)
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[AgentUsage.user_id, AgentUsage.day],
                set_={"turns": AgentUsage.turns + 1},
            )
        )
