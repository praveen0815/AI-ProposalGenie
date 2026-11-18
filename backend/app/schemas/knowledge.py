"""Knowledge document responses. Extracted text is intentionally omitted."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import DocumentFileType, DocumentProcessingStatus, IndexStatus


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    uploaded_by_id: UUID | None
    original_filename: str
    file_type: DocumentFileType
    file_size: int
    processing_status: DocumentProcessingStatus
    character_count: int | None
    page_count: int | None
    processing_error: str | None
    index_status: IndexStatus
    index_error: str | None
    indexed_at: datetime | None
    chunk_count: int | None
    created_at: datetime
    updated_at: datetime


class DocumentStatusResponse(BaseModel):
    id: UUID
    processing_status: DocumentProcessingStatus
    character_count: int | None
    page_count: int | None
    processing_error: str | None
    index_status: IndexStatus
    index_error: str | None
    chunk_count: int | None
    updated_at: datetime
