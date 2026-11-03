import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.database


async def test_ready_reports_database_and_vector_extension(database_client: AsyncClient) -> None:
    response = await database_client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "vector_extension": "ok"}
