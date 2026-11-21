"""Export metadata returned to clients. Storage keys are never included."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.enums import ExportFormat


class ExportResponse(BaseModel):
    id: UUID
    proposal_id: UUID
    format: ExportFormat
    filename: str
    content_type: str
    size_bytes: int
    content_revision: int
    current_revision: int
    stale: bool
    created_at: datetime
