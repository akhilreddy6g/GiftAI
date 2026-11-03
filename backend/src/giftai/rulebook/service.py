from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from giftai.core.errors import NotFoundError
from giftai.rulebook.models import GiftingRule
from giftai.rulebook.repository import RulebookRepository
from giftai.rulebook.retrieval import GiftSituation
from giftai.rulebook.schemas import RuleRead, RulesQuery, SourceCitation


class RulebookService:
    def __init__(self, session: AsyncSession) -> None:
        self._rules = RulebookRepository(session)

    async def rules_for(self, query: RulesQuery) -> Sequence[GiftingRule]:
        return await self._rules.rules_for(
            GiftSituation(
                relationship=query.relationship,
                occasion=query.occasion,
                budget_min_usd=query.budget_min,
                budget_max_usd=query.budget_max,
            )
        )

    async def get(self, rule_id: str) -> GiftingRule:
        """Any rule by id, retired ones included, so old citations still resolve."""
        rule = await self._rules.get(rule_id)
        if rule is None:
            raise NotFoundError("We couldn't find that gifting rule.")
        return rule


def to_rule_read(rule: GiftingRule) -> RuleRead:
    return RuleRead(
        id=rule.id,
        rule=rule.rule,
        rationale=rule.rationale,
        kind=rule.kind,
        relationships=rule.relationships,  # type: ignore[arg-type]  # validated on seed
        occasions=rule.occasions,  # type: ignore[arg-type]
        budget_min_usd=rule.budget_min_usd,
        budget_max_usd=rule.budget_max_usd,
        is_active=rule.is_active,
        sources=[
            SourceCitation(
                id=link.source.id,
                title=link.source.title,
                authors=link.source.authors,
                year=link.source.year,
                kind=link.source.kind,
                location=link.location,
            )
            for link in rule.sources
        ],
    )
