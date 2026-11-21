"""Analytics computed from stored proposals."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_serializer

from app.models.enums import ProposalStatus


class BudgetSummary(BaseModel):
    currency: str
    grand_total: Decimal
    proposal_count: int

    @field_serializer("grand_total")
    def serialize_total(self, value: Decimal) -> str:
        return f"{value:.2f}"


class RecentProposal(BaseModel):
    id: UUID
    title: str
    status: ProposalStatus
    client_name: str | None
    updated_at: datetime


class DashboardSummary(BaseModel):
    company_id: UUID
    total: int
    draft: int
    awaiting_review: int
    approved: int
    sent: int
    archived: int
    rejected: int
    generating: int
    conversion_rate: Decimal | None
    budgets: list[BudgetSummary]
    recent: list[RecentProposal]

    @field_serializer("conversion_rate")
    def serialize_rate(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return f"{value:.4f}"


class TrendPoint(BaseModel):
    month: str
    count: int


class TrendResponse(BaseModel):
    company_id: UUID
    months: list[TrendPoint]


class StatusCount(BaseModel):
    status: ProposalStatus
    count: int


class StatusDistribution(BaseModel):
    company_id: UUID
    statuses: list[StatusCount]
