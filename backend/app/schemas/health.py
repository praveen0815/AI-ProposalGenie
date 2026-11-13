"""Health and readiness response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    status: Literal["ok"]


class DependencyCheck(BaseModel):
    name: str
    status: Literal["up", "down"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    checked_at: datetime
    checks: list[DependencyCheck]
