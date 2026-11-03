"""Health endpoints for the host's health checks and the scheduled keep-alive pings.

They are public on purpose: they reveal only up or down, never configuration.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from giftai.db.session import DatabaseDep
from giftai.health.schemas import CheckStatus, LivenessReport, ReadinessReport
from giftai.health.service import HealthService

router = APIRouter(prefix="/health", tags=["health"])


def get_health_service(database: DatabaseDep) -> HealthService:
    return HealthService(database)


@router.get("/live", summary="The process is up")
async def live() -> LivenessReport:
    return LivenessReport(status=CheckStatus.OK)


@router.get(
    "/ready",
    summary="The process can serve traffic: database reachable and pgvector installed",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessReport}},
)
async def ready(
    response: Response,
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> ReadinessReport:
    report = await health_service.check_readiness()
    if report.status is CheckStatus.FAILING:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
