"""A tiny rulebook and drafts for the rulebook tests."""

from pathlib import Path

from giftai.gifting import Occasion, Relationship
from giftai.rulebook.models import RuleKind
from pipelines.rulebook.document import Rulebook, save_rulebook
from pipelines.rulebook.drafting import Candidate

RULEBOOK = {
    "sources": [
        {
            "id": "gift-science",
            "title": "The Science of Giving",
            "authors": "A. Researcher",
            "year": 2016,
            "kind": "book",
        },
        {
            "id": "office-gifts-2020",
            "title": "Gifts at Work",
            "authors": "B. Scholar, C. Scholar",
            "year": 2020,
            "kind": "paper",
        },
    ],
    "rules": [
        {
            "id": "R-001",
            "rule": "Prefer a gift the recipient asked for over a surprise.",
            "rationale": "Requested gifts are appreciated more than givers expect.",
            "kind": "do",
            "sources": [{"source": "gift-science", "location": "Chapter 2"}],
        },
        {
            "id": "R-002",
            "rule": "Avoid personal or intimate gifts for coworkers.",
            "rationale": "They can make a working relationship awkward.",
            "kind": "dont",
            "relationships": ["coworker", "manager"],
            "sources": [
                {"source": "office-gifts-2020", "location": "Study 1"},
                {"source": "gift-science", "location": "Chapter 5"},
            ],
        },
        {
            "id": "R-003",
            "rule": "For a farewell, pick something useful in the next role or city.",
            "rationale": "It looks forward and gets used, so it is remembered.",
            "kind": "do",
            "occasions": ["farewell"],
            "budget_max_usd": 50,
            "sources": [{"source": "office-gifts-2020", "location": None}],
        },
        {
            "id": "R-004",
            "rule": "Spend on an experience when the budget allows a generous gift.",
            "rationale": "Experiences bring people closer more than objects at that price.",
            "kind": "do",
            "budget_min_usd": 100,
            "sources": [{"source": "gift-science", "location": "Chapter 7"}],
        },
    ],
}


def write_rulebook(path: Path, data: dict[str, object] = RULEBOOK) -> Path:
    save_rulebook(Rulebook.model_validate(data), path)
    return path


def draft(
    candidate_id: str,
    rule: str,
    source_id: str = "gift-science",
    location: str = "Chapter 1",
    kind: RuleKind = RuleKind.DO,
    relationships: list[Relationship] | None = None,
    occasions: list[Occasion] | None = None,
) -> Candidate:
    return Candidate(
        id=candidate_id,
        source_id=source_id,
        location=location,
        rule=rule,
        rationale="Because the research says so, in our own words.",
        kind=kind,
        relationships=relationships or [],
        occasions=occasions or [],
        budget_min_usd=None,
        budget_max_usd=None,
    )
