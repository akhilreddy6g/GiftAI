"""The committed rulebook file and its validation."""

import re
from pathlib import Path
from typing import Annotated, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import RuleKind, SourceKind

# backend/rulebook/rulebook.yaml
RULEBOOK_FILE = Path(__file__).resolve().parents[2] / "rulebook" / "rulebook.yaml"

_HEADER = """\
# The GiftAI gifting rulebook: our own rules, drafted from the sources below and approved
# by a person. Only citations of the sources live here, never their text.
#
# Edit it with `python -m pipelines.rulebook review`, then load it into the database
# with `python -m pipelines.rulebook seed`. Rules removed from this file are retired
# in the database (kept for old citations), never deleted.
"""

SourceId = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=60)]
RuleId = Annotated[str, StringConstraints(pattern=r"^R-\d{3,6}$")]
RuleText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=300)]
_RULE_NUMBER = re.compile(r"^R-(\d+)$")


class SourceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: SourceId
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    authors: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    year: int | None = Field(default=None, ge=1800, le=2100)
    kind: SourceKind


class RuleCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceId
    location: Annotated[str, StringConstraints(max_length=100)] | None = None


class RuleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: RuleId
    rule: RuleText
    rationale: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=600)
    ]
    kind: RuleKind
    # Empty means any.
    relationships: list[Relationship] = []
    occasions: list[Occasion] = []
    budget_min_usd: int | None = Field(default=None, ge=0)
    budget_max_usd: int | None = Field(default=None, ge=0)
    sources: list[RuleCitation] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_budget(self) -> Self:
        if (
            self.budget_min_usd is not None
            and self.budget_max_usd is not None
            and self.budget_min_usd > self.budget_max_usd
        ):
            raise ValueError(f"{self.id}: budget_min_usd is more than budget_max_usd")
        return self


class Rulebook(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[SourceEntry] = []
    rules: list[RuleEntry] = []

    @model_validator(mode="after")
    def _check_references(self) -> Self:
        source_ids = [source.id for source in self.sources]
        rule_ids = [rule.id for rule in self.rules]
        for label, ids in (("source", source_ids), ("rule", rule_ids)):
            duplicates = sorted({item for item in ids if ids.count(item) > 1})
            if duplicates:
                raise ValueError(f"Duplicate {label} ids: {', '.join(duplicates)}")
        known = set(source_ids)
        for rule in self.rules:
            unknown = [citation.source for citation in rule.sources if citation.source not in known]
            if unknown:
                raise ValueError(f"{rule.id} cites unknown sources: {', '.join(unknown)}")
        return self

    def next_rule_id(self) -> str:
        numbers = [
            int(match.group(1)) for rule in self.rules if (match := _RULE_NUMBER.match(rule.id))
        ]
        return f"R-{max(numbers, default=0) + 1:03d}"


def load_rulebook(path: Path = RULEBOOK_FILE) -> Rulebook:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Rulebook.model_validate(data)


def save_rulebook(rulebook: Rulebook, path: Path = RULEBOOK_FILE) -> None:
    data = rulebook.model_dump(mode="json")
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(_HEADER + body, encoding="utf-8")
