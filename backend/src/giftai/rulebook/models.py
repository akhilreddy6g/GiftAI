from enum import StrEnum

from sqlalchemy import ARRAY, Boolean, CheckConstraint, ForeignKey, Integer, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from giftai.db.base import Base, Timestamps
from giftai.db.types import string_enum


class RuleKind(StrEnum):
    DO = "do"
    DONT = "dont"


class SourceKind(StrEnum):
    BOOK = "book"
    PAPER = "paper"
    ARTICLE = "article"


class KnowledgeSource(Timestamps, Base):
    """A book or paper the knowledge base draws on. Only its citation is stored: the
    text itself never leaves the developer's machine.
    """

    __tablename__ = "knowledge_sources"

    # A readable slug, such as "galak-givi-williams-2016".
    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    authors: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer)
    kind: Mapped[SourceKind] = mapped_column(string_enum(SourceKind))


class GiftingRule(Timestamps, Base):
    """One rule of the gifting rulebook, written by us and approved by a person.

    Empty ``relationships`` or ``occasions`` mean the rule applies to any; the budget
    bounds, when set, limit it to gifts in that price range.
    """

    __tablename__ = "gifting_rules"
    __table_args__ = (
        CheckConstraint(
            "budget_min_usd IS NULL OR budget_max_usd IS NULL OR budget_min_usd <= budget_max_usd",
            name="budget_range_ordered",
        ),
    )

    # Stable and citable, such as "R-012": recommendations quote these ids.
    id: Mapped[str] = mapped_column(String(10), primary_key=True)
    rule: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text)
    kind: Mapped[RuleKind] = mapped_column(string_enum(RuleKind))
    relationships: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    occasions: Mapped[list[str]] = mapped_column(ARRAY(String(20)), default=list)
    budget_min_usd: Mapped[int | None] = mapped_column(Integer)
    budget_max_usd: Mapped[int | None] = mapped_column(Integer)
    # Retired rules stay so that old recommendations can still cite them.
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)

    # Always wanted with the rule (they're what "why this gift" cites), so load eagerly.
    sources: Mapped[list["RuleSource"]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="RuleSource.source_id"
    )


class RuleSource(Base):
    """Which sources back a rule, and where in each one."""

    __tablename__ = "rule_sources"

    rule_id: Mapped[str] = mapped_column(
        ForeignKey("gifting_rules.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    # Such as "Chapter 3" or "Study 2"; free text.
    location: Mapped[str | None] = mapped_column(String(100))

    source: Mapped[KnowledgeSource] = relationship(lazy="joined")
