from collections.abc import Sequence

from sqlalchemy import ColumnElement, any_, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from giftai.rulebook.models import GiftingRule
from giftai.rulebook.retrieval import GiftSituation


class RulebookRepository:
    """Answers ``KnowledgeRetriever`` from the gifting_rules table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, rule_id: str) -> GiftingRule | None:
        return await self._session.get(GiftingRule, rule_id)

    async def rules_for(self, situation: GiftSituation) -> Sequence[GiftingRule]:
        conditions: list[ColumnElement[bool]] = [GiftingRule.is_active.is_(True)]
        # An empty tag list means the rule applies to any relationship or occasion.
        if situation.relationship is not None:
            conditions.append(
                or_(
                    func.cardinality(GiftingRule.relationships) == 0,
                    literal(situation.relationship.value) == any_(GiftingRule.relationships),
                )
            )
        if situation.occasion is not None:
            conditions.append(
                or_(
                    func.cardinality(GiftingRule.occasions) == 0,
                    literal(situation.occasion.value) == any_(GiftingRule.occasions),
                )
            )
        # A rule applies when its price range overlaps the giver's budget.
        if situation.budget_max_usd is not None:
            conditions.append(
                or_(
                    GiftingRule.budget_min_usd.is_(None),
                    GiftingRule.budget_min_usd <= situation.budget_max_usd,
                )
            )
        if situation.budget_min_usd is not None:
            conditions.append(
                or_(
                    GiftingRule.budget_max_usd.is_(None),
                    GiftingRule.budget_max_usd >= situation.budget_min_usd,
                )
            )
        rules = await self._session.scalars(
            select(GiftingRule).where(*conditions).order_by(GiftingRule.id)
        )
        return rules.all()
