from typing import Annotated

from fastapi import Depends

from giftai.db.session import DatabaseDep
from giftai.health.service import HealthService


def get_health_service(database: DatabaseDep) -> HealthService:
    return HealthService(database)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
