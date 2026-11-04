"""Drafting is resumable and records where every draft came from."""

from pathlib import Path

from giftai.gifting import Relationship
from giftai.rulebook.models import RuleKind
from pipelines.rulebook.drafting import DraftedRule, draft_candidates, read_candidates
from pipelines.rulebook.extraction import Chapter


class FakeDrafter:
    def __init__(self) -> None:
        self.seen: list[str] = []

    def draft(self, chapter: Chapter, source_title: str) -> list[DraftedRule]:
        self.seen.append(chapter.key)
        if chapter.location == "Preface":
            return []
        return [
            DraftedRule(
                rule=f"Advice from {source_title}, {chapter.location}.",
                rationale="It is what the section argues.",
                kind=RuleKind.DO,
                relationships=[Relationship.FRIEND],
                occasions=[],
                budget_min_usd=None,
                budget_max_usd=None,
            )
        ]


CHAPTERS = [
    Chapter("gift-science", "Preface", "..."),
    Chapter("gift-science", "Chapter 1", "..."),
    Chapter("gift-science", "Chapter 2", "..."),
]
TITLES = {"gift-science": "The Science of Giving"}


def test_drafts_carry_their_source_and_location(tmp_path: Path) -> None:
    candidates_file = tmp_path / "candidates.jsonl"

    drafted = draft_candidates(CHAPTERS, TITLES, FakeDrafter(), candidates_file)

    candidates = read_candidates(candidates_file)
    assert drafted == 3
    assert [(c.source_id, c.location) for c in candidates] == [
        ("gift-science", "Chapter 1"),
        ("gift-science", "Chapter 2"),
    ]
    assert candidates[0].rule == "Advice from The Science of Giving, Chapter 1."
    assert len({c.id for c in candidates}) == 2


def test_a_second_run_only_drafts_new_sections(tmp_path: Path) -> None:
    candidates_file = tmp_path / "candidates.jsonl"
    draft_candidates(CHAPTERS[:2], TITLES, FakeDrafter(), candidates_file)
    drafter = FakeDrafter()

    drafted = draft_candidates(CHAPTERS, TITLES, drafter, candidates_file)

    # The preface drafted nothing the first time, and is still not asked again.
    assert drafter.seen == ["gift-science|Chapter 2"]
    assert drafted == 1
    assert len(read_candidates(candidates_file)) == 2


def test_no_drafts_yet_reads_as_empty(tmp_path: Path) -> None:
    assert read_candidates(tmp_path / "missing.jsonl") == []
