"""Proposal request and response schemas."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import ProposalStatus

_OPTIONAL_TEXT = (
    "client_industry",
    "project_description",
    "business_objectives",
    "scope_of_work",
    "deliverables",
    "timeline",
    "budget_range",
    "currency",
    "payment_terms",
    "additional_instructions",
)


class ProposalCreate(BaseModel):
    company_id: UUID
    client_name: str = Field(min_length=1, max_length=200)
    client_industry: str | None = Field(default=None, max_length=200)
    client_requirements: str = Field(min_length=1, max_length=8000)
    project_title: str = Field(min_length=1, max_length=300)
    project_description: str | None = Field(default=None, max_length=8000)
    business_objectives: str | None = Field(default=None, max_length=4000)
    scope_of_work: str | None = Field(default=None, max_length=8000)
    deliverables: str | None = Field(default=None, max_length=4000)
    timeline: str | None = Field(default=None, max_length=1000)
    budget_range: str | None = Field(default=None, max_length=200)
    currency: str | None = Field(default=None, max_length=3)
    payment_terms: str | None = Field(default=None, max_length=1000)
    additional_instructions: str | None = Field(default=None, max_length=4000)

    @field_validator(
        "client_name",
        "client_requirements",
        "project_title",
        *_OPTIONAL_TEXT,
    )
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("client_name", "client_requirements", "project_title")
    @classmethod
    def required_text(cls, value: str | None) -> str:
        if not value:
            raise ValueError("This field is required")
        return value

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = value.upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return code


class ProposalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    summary: str | None = Field(default=None, max_length=4000)
    status: ProposalStatus | None = None

    @field_validator("title", "summary")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("status")
    @classmethod
    def status_is_user_settable(cls, value: ProposalStatus | None) -> ProposalStatus | None:
        if value == ProposalStatus.GENERATING:
            raise ValueError("Generation status is set by the server")
        return value


class SourceReference(BaseModel):
    document_id: UUID
    filename: str
    chunk_index: int | None = None


class TokenUsageResponse(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ProposalSectionResponse(BaseModel):
    id: UUID
    title: str
    body: str
    position: int
    needs_review: bool
    review_notes: str | None
    ai_body: str | None = None
    origin: str = "user"
    source_references: list[SourceReference]


class ProposalResponse(BaseModel):
    id: UUID
    company_id: UUID
    client_id: UUID | None
    title: str
    summary: str | None
    status: ProposalStatus
    client_name: str | None
    model_name: str | None
    prompt_version: str | None
    retrieval_status: str | None
    token_usage: TokenUsageResponse | None
    generation_error: str | None
    generation_input: dict[str, Any] | None
    source_references: list[SourceReference]
    sections: list[ProposalSectionResponse]
    content_revision: int = 0
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProposalSummary(BaseModel):
    id: UUID
    company_id: UUID
    title: str
    summary: str | None
    status: ProposalStatus
    client_name: str | None
    generation_error: str | None
    generated_at: datetime | None
    created_at: datetime
    updated_at: datetime
