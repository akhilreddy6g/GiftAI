import pytest
from httpx import AsyncClient

from tests.api.conftest import Headers, create_recipient

pytestmark = pytest.mark.database


async def test_recipient_lifecycle(database_client: AsyncClient, alice: Headers) -> None:
    created = await create_recipient(
        database_client, alice, name="Priya", relationship="friend", interests=["tea", "Tea"]
    )
    assert created["interests"] == ["tea"]

    updated = await database_client.patch(
        f"/api/v1/recipients/{created['id']}", json={"notes": "Loves oolong"}, headers=alice
    )
    assert updated.status_code == 200
    assert updated.json()["notes"] == "Loves oolong"
    assert updated.json()["name"] == "Priya"

    deleted = await database_client.delete(f"/api/v1/recipients/{created['id']}", headers=alice)
    assert deleted.status_code == 204
    gone = await database_client.get(f"/api/v1/recipients/{created['id']}", headers=alice)
    assert gone.status_code == 404


async def test_users_cannot_see_each_others_recipients(
    database_client: AsyncClient, alice: Headers, bob: Headers
) -> None:
    alices = await create_recipient(database_client, alice)

    for method in ("get", "patch", "delete"):
        response = await database_client.request(
            method,
            f"/api/v1/recipients/{alices['id']}",
            headers=bob,
            json={"notes": "hijacked"} if method == "patch" else None,
        )
        assert response.status_code == 404

    listing = await database_client.get("/api/v1/recipients", headers=bob)
    assert listing.json()["items"] == []


async def test_recipients_are_paginated(database_client: AsyncClient, alice: Headers) -> None:
    for name in ("A", "B", "C"):
        await create_recipient(database_client, alice, name=name)

    first = (await database_client.get("/api/v1/recipients?limit=2", headers=alice)).json()
    second = (
        await database_client.get(
            f"/api/v1/recipients?limit=2&cursor={first['next_cursor']}", headers=alice
        )
    ).json()

    assert [item["name"] for item in first["items"]] == ["C", "B"]
    assert [item["name"] for item in second["items"]] == ["A"]
    assert second["next_cursor"] is None


async def test_invalid_input_explains_the_problem(
    database_client: AsyncClient, alice: Headers
) -> None:
    response = await database_client.post(
        "/api/v1/recipients", json={"name": "Mom", "relationship": "nemesis"}, headers=alice
    )

    assert response.status_code == 422
    assert response.json()["error"]["message"].startswith("relationship:")
