"""Retrieval and grounded-answer responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import IndexStatus


class IndexResponse(BaseModel):
    document_id: UUID
    index_status: IndexStatus
    chunk_count: int | None
    index_error: str | None
    indexed_at: datetime | None
    already_indexed: bool


class SearchRequest(BaseModel):
    company_id: UUID
    query: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class QueryRequest(BaseModel):
    company_id: UUID
    question: str = Field(min_length=1, max_length=2000)
    document_ids: list[UUID] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    similarity_threshold: float | None = Field(default=None, ge=0, le=1)


class RetrievedChunkResponse(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int
    page_number: int | None
    source: str
    text: str
    score: float


class SourceDocument(BaseModel):
    document_id: UUID
    filename: str
    chunk_indexes: list[int]


class SearchResponse(BaseModel):
    results: list[RetrievedChunkResponse]


class QueryResponse(BaseModel):
    answer: str
    context: list[RetrievedChunkResponse]
    sources: list[SourceDocument]
