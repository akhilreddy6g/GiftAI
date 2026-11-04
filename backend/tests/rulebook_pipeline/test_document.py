"""The committed rulebook file: its checks, ids and round trip."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from pipelines.rulebook.document import RULEBOOK_FILE, Rulebook, load_rulebook
from tests.rulebook_samples import RULEBOOK, write_rulebook


def test_the_committed_rulebook_is_valid() -> None:
    load_rulebook(RULEBOOK_FILE)


def test_a_rulebook_survives_saving_and_loading(tmp_path: Path) -> None:
    path = write_rulebook(tmp_path / "rulebook.yaml")

    assert load_rulebook(path) == Rulebook.model_validate(RULEBOOK)
    assert path.read_text().startswith("# The GiftAI gifting rulebook")


def test_new_rule_ids_continue_after_the_highest() -> None:
    assert Rulebook.model_validate(RULEBOOK).next_rule_id() == "R-005"
    assert Rulebook().next_rule_id() == "R-001"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda book: book["rules"].append(copy.deepcopy(book["rules"][0])), "Duplicate rule"),
        (lambda book: book["rules"][0]["sources"].append({"source": "nope"}), "unknown sources"),
        (lambda book: book["rules"][3].update(budget_max_usd=20), "budget_min_usd is more"),
        (lambda book: book["rules"][0].update(relationships=["boss"]), "relationships"),
        (lambda book: book["rules"][0].update(sources=[]), "sources"),
        (lambda book: book["rules"][0].update(id="12"), "id"),
        (lambda book: book["sources"][0].update(id="Not A Slug"), "id"),
    ],
)
def test_mistakes_in_the_rulebook_are_caught(change: Callable[[Any], object], message: str) -> None:
    book = copy.deepcopy(RULEBOOK)
    change(book)

    with pytest.raises(ValidationError, match=message):
        Rulebook.model_validate(book)
