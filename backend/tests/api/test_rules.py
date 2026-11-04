"""The rulebook API, on rules loaded by the real seeding step."""

from collections.abc import Callable
from pathlib import Path

import pytest
from httpx import AsyncClient

from pipelines.rulebook import steps
from tests.api.conftest import Headers
from tests.rulebook_samples import RULEBOOK, write_rulebook


@pytest.fixture(scope="module")
def rulebook(test_database_url: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = write_rulebook(tmp_path_factory.mktemp("rulebook") / "rulebook.yaml")
    steps.seed(path, test_database_url)
    return path


@pytest.fixture
def user(rulebook: Path, new_user: Callable[[], Headers]) -> Headers:
    return new_user()


async def rule_ids(client: AsyncClient, headers: Headers, **params: str | int) -> list[str]:
    response = await client.get("/api/v1/rules", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return [rule["id"] for rule in response.json()["items"]]


async def test_rules_apply_by_relationship_occasion_and_budget(
    database_client: AsyncClient, user: Headers
) -> None:
    assert await rule_ids(database_client, user) == ["R-001", "R-002", "R-003", "R-004"]
    assert await rule_ids(database_client, user, relationship="friend") == [
        "R-001",
        "R-003",
        "R-004",
    ]
    assert await rule_ids(
        database_client, user, relationship="coworker", occasion="farewell", budget_max=30
    ) == ["R-001", "R-002", "R-003"]
    assert await rule_ids(database_client, user, occasion="birthday", budget_min=120) == [
        "R-001",
        "R-002",
        "R-004",
    ]


async def test_a_rule_comes_with_its_cited_sources(
    database_client: AsyncClient, user: Headers
) -> None:
    response = await database_client.get("/api/v1/rules/R-002", headers=user)

    assert response.status_code == 200
    rule = response.json()
    assert rule["kind"] == "dont"
    assert rule["relationships"] == ["coworker", "manager"]
    assert [(s["id"], s["location"]) for s in rule["sources"]] == [
        ("gift-science", "Chapter 5"),
        ("office-gifts-2020", "Study 1"),
    ]
    assert rule["sources"][1]["title"] == "Gifts at Work"


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/api/v1/rules/R-999", 404),
        ("/api/v1/rules/not-a-rule", 422),
        ("/api/v1/rules?budget_min=50&budget_max=10", 422),
        ("/api/v1/rules?relationship=boss", 422),
    ],
)
async def test_bad_requests_are_refused(
    database_client: AsyncClient, user: Headers, path: str, status: int
) -> None:
    response = await database_client.get(path, headers=user)

    assert response.status_code == status


async def test_rules_need_a_signed_in_user(database_client: AsyncClient, rulebook: Path) -> None:
    response = await database_client.get("/api/v1/rules")

    assert response.status_code == 401


async def test_reseeding_retires_removed_rules_and_restores_them(
    database_client: AsyncClient, user: Headers, rulebook: Path, test_database_url: str
) -> None:
    trimmed = {**RULEBOOK, "rules": RULEBOOK["rules"][:2]}  # type: ignore[index]
    smaller = write_rulebook(rulebook.parent / "smaller.yaml", trimmed)
    edited = {
        **RULEBOOK,
        "rules": [
            {**RULEBOOK["rules"][0], "sources": [{"source": "office-gifts-2020"}]},  # type: ignore[index]
            *RULEBOOK["rules"][1:],  # type: ignore[index]
        ],
    }

    try:
        report = steps.seed(smaller, test_database_url)
        assert (report.active_rules, report.retired_rules) == (2, 2)
        assert await rule_ids(database_client, user) == ["R-001", "R-002"]
        retired = await database_client.get("/api/v1/rules/R-003", headers=user)
        assert retired.json()["is_active"] is False

        steps.seed(write_rulebook(rulebook.parent / "edited.yaml", edited), test_database_url)
        rule = (await database_client.get("/api/v1/rules/R-001", headers=user)).json()
        assert [source["id"] for source in rule["sources"]] == ["office-gifts-2020"]
        assert rule["sources"][0]["location"] is None
    finally:
        steps.seed(rulebook, test_database_url)
    assert await rule_ids(database_client, user) == ["R-001", "R-002", "R-003", "R-004"]
