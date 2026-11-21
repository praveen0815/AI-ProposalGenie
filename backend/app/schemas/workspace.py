"""Editing, version, cost, and approval payloads."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer, field_validator

from app.models.enums import ApprovalAction, CostSource, ProposalStatus
from app.schemas.proposal import ProposalResponse, ProposalSectionResponse


class DraftSectionWrite(BaseModel):
    id: UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(default="", max_length=20000)

    @field_validator("title", "body")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def title_present(cls, value: str) -> str:
        if not value:
            raise ValueError("Title is required")
        return value


class DraftSave(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    expected_revision: int = Field(ge=0)
    sections: list[DraftSectionWrite] = Field(default_factory=list, max_length=40)

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Title is required")
        return stripped


class VersionCreate(BaseModel):
    change_description: str = Field(min_length=1, max_length=500)

    @field_validator("change_description")
    @classmethod
    def strip_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Describe what changed")
        return stripped


class VersionSummary(BaseModel):
    id: UUID
    proposal_id: UUID
    version_number: int
    change_description: str | None
    created_by_id: UUID | None
    created_at: datetime


class VersionDetail(VersionSummary):
    snapshot: dict


class VersionChange(BaseModel):
    title: str
    change: str
    left: str | None = None
    right: str | None = None


class VersionComparison(BaseModel):
    left_version_id: UUID
    right_version_id: UUID
    title_changed: bool
    changes: list[VersionChange]


class RegenerateRequest(BaseModel):
    confirm_overwrite: bool = False


class RegenerateResponse(BaseModel):
    applied: bool
    suggested_body: str
    previous_body: str
    ai_body: str | None
    section: ProposalSectionResponse | None = None
    proposal: ProposalResponse | None = None


class CostLineWrite(BaseModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    category: str = Field(default="General", min_length=1, max_length=80)
    quantity: Decimal = Field(gt=0, le=1_000_000)
    unit: str = Field(min_length=1, max_length=40)
    unit_price: Decimal = Field(ge=0, le=10_000_000)
    duration: Decimal = Field(default=Decimal("1"), gt=0, le=10_000)
    tax_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    source: CostSource = CostSource.CONFIRMED

    @field_validator("name", "category", "unit")
    @classmethod
    def strip_label(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required")
        return stripped


class CostSheetWrite(BaseModel):
    currency: str = Field(min_length=3, max_length=3)
    lines: list[CostLineWrite] = Field(default_factory=list, max_length=100)

    @field_validator("currency")
    @classmethod
    def currency_code(cls, value: str) -> str:
        code = value.strip().upper()
        if len(code) != 3 or not code.isalpha():
            raise ValueError("Currency must be a three-letter code")
        return code


class CostLineResponse(BaseModel):
    id: UUID
    name: str
    category: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    duration: Decimal
    tax_percent: Decimal
    discount_percent: Decimal
    currency: str
    source: CostSource
    base: Decimal
    discount: Decimal
    tax: Decimal
    subtotal: Decimal
    position: int
    confirmed_at: datetime | None

    @field_serializer(
        "quantity",
        "unit_price",
        "duration",
        "tax_percent",
        "discount_percent",
        "base",
        "discount",
        "tax",
        "subtotal",
    )
    def serialize_decimal(self, value: Decimal) -> str:
        return f"{value:.2f}" if value == value.quantize(Decimal("0.01")) else f"{value:.3f}"


class CostSheetResponse(BaseModel):
    currency: str | None
    lines: list[CostLineResponse]
    base: Decimal
    discount: Decimal
    tax: Decimal
    grand_total: Decimal
    estimated_count: int
    confirmed_count: int

    @field_serializer("base", "discount", "tax", "grand_total")
    def serialize_money(self, value: Decimal) -> str:
        return f"{value:.2f}"


class ApprovalRequest(BaseModel):
    action: ApprovalAction
    comment: str | None = Field(default=None, max_length=2000)

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class ApprovalEventResponse(BaseModel):
    id: UUID
    action: ApprovalAction
    from_status: ProposalStatus
    to_status: ProposalStatus
    comment: str | None
    actor_id: UUID | None
    created_at: datetime
