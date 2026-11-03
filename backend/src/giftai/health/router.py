"""Health endpoints for the host's health checks and the scheduled keep-alive pings.

They are public on purpose: they reveal only up or down, never configuration.
"""

from fastapi import APIRouter, Response, status

from giftai.health.dependencies import HealthServiceDep
from giftai.health.schemas import CheckStatus, LivenessReport, ReadinessReport

router = APIRouter(prefix="/health", tags=["health"])


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
    health_service: HealthServiceDep,
) -> ReadinessReport:
    report = await health_service.check_readiness()
    if report.status is CheckStatus.FAILING:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
