"""Loads the approved rulebook into the database in one transaction.

Sources and rules are upserted; rules no longer in the file are retired (kept, so that
old recommendations can still cite them) and come back if they are re-added.
"""

import logging
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from giftai.rulebook.models import GiftingRule, KnowledgeSource, RuleSource
from pipelines.rulebook.document import Rulebook

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedReport:
    sources: int
    active_rules: int
    retired_rules: int


def seed_rulebook(session: Session, rulebook: Rulebook) -> SeedReport:
    with session.begin():
        for source in rulebook.sources:
            session.merge(
                KnowledgeSource(
                    id=source.id,
                    title=source.title,
                    authors=source.authors,
                    year=source.year,
                    kind=source.kind,
                )
            )
        session.flush()

        for entry in rulebook.rules:
            rule = session.get(GiftingRule, entry.id) or GiftingRule(id=entry.id)
            rule.rule = entry.rule
            rule.rationale = entry.rationale
            rule.kind = entry.kind
            rule.relationships = [relationship.value for relationship in entry.relationships]
            rule.occasions = [occasion.value for occasion in entry.occasions]
            rule.budget_min_usd = entry.budget_min_usd
            rule.budget_max_usd = entry.budget_max_usd
            rule.is_active = True
            _sync_citations(rule, {c.source: c.location for c in entry.sources})
            session.add(rule)
        session.flush()

        keep = [entry.id for entry in rulebook.rules]
        retired = len(
            session.scalars(
                update(GiftingRule)
                .where(GiftingRule.is_active.is_(True), GiftingRule.id.not_in(keep))
                .values(is_active=False)
                .returning(GiftingRule.id)
            ).all()
        )
        active = len(session.scalars(select(GiftingRule.id).where(GiftingRule.is_active)).all())
    return SeedReport(len(rulebook.sources), active, retired)


def _sync_citations(rule: GiftingRule, wanted: dict[str, str | None]) -> None:
    """Edits the rule's citations in place: replacing them wholesale would delete and
    re-insert rows with the same key in one flush.
    """
    current = {citation.source_id: citation for citation in rule.sources}
    for source_id, citation in current.items():
        if source_id not in wanted:
            rule.sources.remove(citation)
    for source_id, location in wanted.items():
        if source_id in current:
            current[source_id].location = location
        else:
            rule.sources.append(RuleSource(source_id=source_id, location=location))
