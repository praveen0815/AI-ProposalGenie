"""Agent workflow API schemas."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentNodeStatus(BaseModel):
    key: str
    label: str
    status: Literal["pending", "running", "completed", "failed"]


class AgentStatusResponse(BaseModel):
    proposal_id: UUID
    run_id: UUID | None = None
    status: Literal["NOT_STARTED", "RUNNING", "COMPLETED", "FAILED"]
    current_node: str | None = None
    iteration: int = 0
    max_iterations: int = 0
    nodes: list[AgentNodeStatus]
    review: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    external_research_status: str | None = None
    review_limit_reached: bool = False
    error: str | None = None


class AgentEventResponse(BaseModel):
    id: UUID
    run_id: UUID
    node: str
    phase: str
    message: str
    payload: dict[str, Any]
    created_at: datetime
