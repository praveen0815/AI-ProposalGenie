"""Liveness is mounted at the application root. These routes report dependencies."""

from fastapi import APIRouter, Response, status

from app.schemas.health import HealthResponse
from app.services.health import collect_health

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Return application and dependency status. Always HTTP 200 when the process can respond."""

    return collect_health()


@router.get("/ready", response_model=HealthResponse)
def readiness(response: Response) -> HealthResponse:
    """Return 200 when PostgreSQL and Redis are reachable, otherwise 503."""

    report = collect_health()
    if report.status != "ok":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
