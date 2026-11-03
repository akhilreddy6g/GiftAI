"""Grouping similar drafts, and the review that turns them into rules."""

from pathlib import Path

from giftai.rulebook.models import RuleKind, SourceKind
from pipelines.rulebook.document import load_rulebook
from pipelines.rulebook.drafting import Candidate
from pipelines.rulebook.grouping import group_candidates, read_groups, write_groups
from pipelines.rulebook.review import REJECTED, Review, run_review
from pipelines.rulebook.sources import LocalSource
from tests.fakes import HashingTextEmbedder
from tests.rulebook_samples import draft, write_rulebook

SAME = "Give the gift they asked for instead of a surprise."
DRAFTS = [
    draft("C-1", SAME, "gift-science", "Chapter 2"),
    draft("C-2", "Skip gift cards for close family.", "gift-science", "Chapter 4"),
    draft("C-3", SAME, "registry-study", "Study 1"),
    draft("C-4", SAME, "registry-study", "Study 3"),
    draft("C-5", SAME, "registry-study", "Study 3", kind=RuleKind.DONT),
]
SOURCES = [
    LocalSource(
        id="gift-science",
        title="The Science of Giving",
        authors="A. Researcher",
        year=2016,
        kind=SourceKind.BOOK,
        file=Path("gift-science.pdf"),
    ),
    LocalSource(
        id="registry-study",
        title="Registries and Regret",
        authors="D. Author",
        year=2011,
        kind=SourceKind.PAPER,
        file=Path("registry.pdf"),
    ),
]


def test_the_same_advice_is_grouped_across_sources(tmp_path: Path) -> None:
    groups = group_candidates(DRAFTS, HashingTextEmbedder())

    # Advice backed by two sources comes first; "do" and "don't" never merge.
    assert [group.candidate_ids for group in groups] == [
        ("C-1", "C-3", "C-4"),
        ("C-2",),
        ("C-5",),
    ]
    write_groups(tmp_path / "groups.json", groups)
    assert read_groups(tmp_path / "groups.json") == groups


def make_review(tmp_path: Path) -> Review:
    rulebook = tmp_path / "rulebook.yaml"
    if not rulebook.exists():
        write_rulebook(rulebook, {"sources": [], "rules": []})
    groups = group_candidates(DRAFTS, HashingTextEmbedder())
    return Review(DRAFTS, groups, SOURCES, rulebook, tmp_path / "review.json")


def test_accepting_cites_every_source_in_the_group(tmp_path: Path) -> None:
    review = make_review(tmp_path)
    drafts = review.pending()[0]

    entry = review.accept(drafts, drafts[1])

    saved = load_rulebook(tmp_path / "rulebook.yaml")
    assert entry.id == "R-001"
    assert saved.rules == [entry]
    assert [(c.source, c.location) for c in entry.sources] == [
        ("gift-science", "Chapter 2"),
        ("registry-study", "Study 1; Study 3"),
    ]
    # Sources are added the first time a rule cites them, without the local file path.
    assert [source.id for source in saved.sources] == ["gift-science", "registry-study"]


def test_review_resumes_where_it_stopped(tmp_path: Path) -> None:
    review = make_review(tmp_path)
    first, second, _ = review.pending()
    review.accept(first, first[0])
    review.reject(second)

    resumed = make_review(tmp_path)

    assert [[d.id for d in drafts] for drafts in resumed.pending()] == [["C-5"]]
    assert resumed.state.decisions["C-2"] == REJECTED
    assert resumed.rulebook.next_rule_id() == "R-002"


def test_the_review_prompt_accepts_edits_rejects_and_quits(tmp_path: Path) -> None:
    review = make_review(tmp_path)
    answers = iter(["9", "e1", "r", "q"])
    output: list[str] = []

    def edit(chosen: Candidate) -> Candidate:
        return chosen.model_copy(update={"rule": "Ask what they want, then give exactly that."})

    run_review(review, ask=lambda _: next(answers), say=output.append, edit=edit)

    rules = load_rulebook(tmp_path / "rulebook.yaml").rules
    assert [rule.rule for rule in rules] == ["Ask what they want, then give exactly that."]
    assert review.state.decisions == {
        "C-1": "R-001",
        "C-3": "R-001",
        "C-4": "R-001",
        "C-2": REJECTED,
    }
    assert any("Saved as R-001." in line for line in output)


def test_an_invalid_edit_is_not_saved(tmp_path: Path) -> None:
    review = make_review(tmp_path)
    answers = iter(["e1", "s", "q"])
    output: list[str] = []

    def edit(chosen: Candidate) -> Candidate:
        return chosen.model_copy(update={"rule": "Too short"})

    run_review(review, ask=lambda _: next(answers), say=output.append, edit=edit)

    assert load_rulebook(tmp_path / "rulebook.yaml").rules == []
    assert review.state.decisions == {}
    assert any(line.startswith("Not saved:") for line in output)
