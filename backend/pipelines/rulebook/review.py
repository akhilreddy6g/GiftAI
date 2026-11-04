"""The review step: a person accepts, edits or rejects each group of drafted rules.

Every decision is saved straight away, to the rulebook file and to a record of which
drafts were decided, so a review can stop at any point and pick up where it left off.
Decisions are kept per draft, so regrouping after adding a source keeps them.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pipelines.rulebook.document import (
    Rulebook,
    RuleCitation,
    RuleEntry,
    SourceEntry,
    load_rulebook,
    save_rulebook,
)
from pipelines.rulebook.drafting import Candidate
from pipelines.rulebook.grouping import CandidateGroup
from pipelines.rulebook.sources import LocalSource

REJECTED = "rejected"


@dataclass
class ReviewState:
    """Draft id to the rule it became, or "rejected"."""

    decisions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "ReviewState":
        if not path.exists():
            return cls()
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.decisions, indent=1, sort_keys=True), encoding="utf-8")


class Review:
    def __init__(
        self,
        candidates: list[Candidate],
        groups: list[CandidateGroup],
        sources: list[LocalSource],
        rulebook_file: Path,
        state_file: Path,
    ) -> None:
        listed = {source.id for source in sources}
        unknown = sorted({c.source_id for c in candidates if c.source_id not in listed})
        if unknown:
            raise ValueError(
                f"The drafts cite sources missing from sources.yaml: {', '.join(unknown)}. "
                "Run the 'draft' step again (it drops drafts of removed or renamed sources), "
                "then 'group', then 'review'."
            )
        self._candidates = {candidate.id: candidate for candidate in candidates}
        self._groups = groups
        self._sources = {source.id: source for source in sources}
        self._rulebook_file = rulebook_file
        self._state_file = state_file
        self.rulebook = load_rulebook(rulebook_file)
        self.state = ReviewState.load(state_file)

    def pending(self) -> list[list[Candidate]]:
        """Groups with any undecided draft, as their drafts."""
        pending = []
        for group in self._groups:
            drafts = [self._candidates[i] for i in group.candidate_ids if i in self._candidates]
            if any(draft.id not in self.state.decisions for draft in drafts):
                pending.append(drafts)
        return pending

    def accept(self, drafts: list[Candidate], chosen: Candidate) -> RuleEntry:
        """Adds the chosen wording as a new rule citing every source in the group."""
        locations: dict[str, list[str]] = {}
        for draft in drafts:
            places = locations.setdefault(draft.source_id, [])
            if draft.location not in places:
                places.append(draft.location)
        entry = RuleEntry(
            id=self.rulebook.next_rule_id(),
            rule=chosen.rule,
            rationale=chosen.rationale,
            kind=chosen.kind,
            relationships=chosen.relationships,
            occasions=chosen.occasions,
            budget_min_usd=chosen.budget_min_usd,
            budget_max_usd=chosen.budget_max_usd,
            sources=[
                RuleCitation(source=source_id, location=_join_locations(places))
                for source_id, places in locations.items()
            ],
        )
        known = {source.id for source in self.rulebook.sources}
        new_sources = [
            SourceEntry.model_validate(self._sources[source_id].model_dump(exclude={"file"}))
            for source_id in locations
            if source_id not in known
        ]
        # Validate the whole book before writing anything.
        self.rulebook = Rulebook(
            sources=[*self.rulebook.sources, *new_sources], rules=[*self.rulebook.rules, entry]
        )
        save_rulebook(self.rulebook, self._rulebook_file)
        self._decide(drafts, entry.id)
        return entry

    def reject(self, drafts: list[Candidate]) -> None:
        self._decide(drafts, REJECTED)

    def _decide(self, drafts: list[Candidate], outcome: str) -> None:
        for draft in drafts:
            self.state.decisions[draft.id] = outcome
        self.state.save(self._state_file)


def _join_locations(places: list[str]) -> str:
    joined = "; ".join(places)
    return joined if len(joined) <= 100 else joined[:97] + "..."


HELP = """\
  1-9   accept that wording          e1-e9  edit that wording first
  r     reject the group             s      skip for now
  q     quit (progress is saved)"""


def run_review(
    review: Review,
    ask: Callable[[str], str] = input,
    say: Callable[[str], None] = print,
    edit: Callable[[Candidate], Candidate | None] | None = None,
) -> None:
    pending = review.pending()
    say(f"{len(pending)} groups to review, {len(review.rulebook.rules)} rules so far.\n{HELP}")
    for number, drafts in enumerate(pending, 1):
        sources = len({draft.source_id for draft in drafts})
        say(f"\nGroup {number} of {len(pending)}: {len(drafts)} drafts from {sources} sources")
        for index, draft in enumerate(drafts, 1):
            say(_describe(index, draft))
        while True:
            answer = ask("> ").strip().lower()
            if answer == "q":
                return
            if answer == "s":
                break
            if answer == "r":
                review.reject(drafts)
                break
            chosen = _pick(answer, drafts)
            if chosen is None:
                say(HELP)
                continue
            try:
                if answer.startswith("e"):
                    if edit is None:
                        say("Editing needs a terminal editor ($EDITOR).")
                        continue
                    edited = edit(chosen)
                    if edited is None:
                        say("Nothing changed; pick again.")
                        continue
                    chosen = edited
                entry = review.accept(drafts, chosen)
            except ValueError as error:
                say(f"Not saved: {error}")
                continue
            say(f"Saved as {entry.id}.")
            break
    say(f"\nDone for now: {len(review.rulebook.rules)} rules in the rulebook.")


def _pick(answer: str, drafts: list[Candidate]) -> Candidate | None:
    digits = answer.removeprefix("e")
    if digits.isdigit() and 1 <= int(digits) <= len(drafts):
        return drafts[int(digits) - 1]
    return None


def _describe(index: int, draft: Candidate) -> str:
    scope = [
        ", ".join(draft.relationships) or "anyone",
        ", ".join(draft.occasions) or "any occasion",
    ]
    if draft.budget_min_usd is not None or draft.budget_max_usd is not None:
        low = "" if draft.budget_min_usd is None else f"${draft.budget_min_usd}"
        high = "" if draft.budget_max_usd is None else f"${draft.budget_max_usd}"
        scope.append(f"{low}-{high}")
    return (
        f" [{index}] {draft.kind.value.upper()}: {draft.rule}\n"
        f"     why: {draft.rationale}\n"
        f"     for: {'; '.join(scope)}  ({draft.source_id}, {draft.location})"
    )
