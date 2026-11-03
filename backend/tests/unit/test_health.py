from httpx import AsyncClient


async def test_live_needs_no_database(offline_client: AsyncClient) -> None:
    response = await offline_client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_reports_failure_when_database_is_unreachable(
    offline_client: AsyncClient,
) -> None:
    response = await offline_client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "failing",
        "database": "failing",
        "vector_extension": "failing",
    }
