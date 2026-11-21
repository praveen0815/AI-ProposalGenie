"""Company analytics from stored proposals and cost lines."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ProposalStatus
from app.models.proposal import Proposal, ProposalCostItem
from app.models.user import User
from app.proposals.costing import line_amounts, money
from app.repositories import memberships as membership_repository
from app.schemas.dashboard import (
    BudgetSummary,
    DashboardSummary,
    RecentProposal,
    StatusCount,
    StatusDistribution,
    TrendPoint,
    TrendResponse,
)


def summary(db: Session, actor: User, company_id: UUID) -> DashboardSummary:
    _member(db, company_id, actor)
    counts = _counts(db, company_id)
    approved = counts[ProposalStatus.APPROVED]
    sent = counts[ProposalStatus.SENT]
    basis = approved + sent
    rate = None if basis == 0 else (Decimal(sent) / Decimal(basis)).quantize(Decimal("0.0001"))
    return DashboardSummary(
        company_id=company_id,
        total=sum(counts.values()),
        draft=counts[ProposalStatus.DRAFT],
        awaiting_review=counts[ProposalStatus.REVIEW],
        approved=approved,
        sent=sent,
        archived=counts[ProposalStatus.ARCHIVED],
        rejected=counts[ProposalStatus.REJECTED],
        generating=counts[ProposalStatus.GENERATING],
        conversion_rate=rate,
        budgets=_budgets(db, company_id),
        recent=_recent(db, company_id),
    )


def trends(db: Session, actor: User, company_id: UUID) -> TrendResponse:
    _member(db, company_id, actor)
    month = func.date_trunc("month", Proposal.created_at)
    rows = db.execute(
        select(month, func.count())
        .where(Proposal.company_id == company_id)
        .group_by(month)
        .order_by(month.asc())
    ).all()
    found = {_month_key(value): int(count) for value, count in rows if value is not None}
    return TrendResponse(company_id=company_id, months=[TrendPoint(month=key, count=found.get(key, 0)) for key in _recent_months()])


def status_distribution(db: Session, actor: User, company_id: UUID) -> StatusDistribution:
    _member(db, company_id, actor)
    counts = _counts(db, company_id)
    return StatusDistribution(
        company_id=company_id,
        statuses=[StatusCount(status=item, count=counts[item]) for item in ProposalStatus],
    )


def _member(db: Session, company_id: UUID, actor: User) -> None:
    if membership_repository.get_for_user(db, company_id, actor.id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")


def _counts(db: Session, company_id: UUID) -> dict[ProposalStatus, int]:
    rows = db.execute(
        select(Proposal.status, func.count()).where(Proposal.company_id == company_id).group_by(Proposal.status)
    ).all()
    counts = {item: 0 for item in ProposalStatus}
    for proposal_status, count in rows:
        counts[ProposalStatus(proposal_status)] = int(count)
    return counts


def _budgets(db: Session, company_id: UUID) -> list[BudgetSummary]:
    rows = db.scalars(select(ProposalCostItem).where(ProposalCostItem.company_id == company_id)).all()
    buckets: dict[str, dict[str, object]] = {}
    for row in rows:
        amounts = line_amounts(
            Decimal(row.quantity),
            Decimal(row.unit_price),
            Decimal(row.duration),
            Decimal(row.tax_percent),
            Decimal(row.discount_percent),
        )
        bucket = buckets.setdefault(row.currency, {"total": Decimal("0.00"), "proposals": set()})
        bucket["total"] = Decimal(bucket["total"]) + amounts["subtotal"]
        proposals = bucket["proposals"]
        assert isinstance(proposals, set)
        proposals.add(row.proposal_id)
    summaries = []
    for currency in sorted(buckets):
        bucket = buckets[currency]
        proposals = bucket["proposals"]
        assert isinstance(proposals, set)
        summaries.append(
            BudgetSummary(
                currency=currency,
                grand_total=money(Decimal(bucket["total"])),
                proposal_count=len(proposals),
            )
        )
    return summaries


def _recent(db: Session, company_id: UUID) -> list[RecentProposal]:
    rows = db.scalars(
        select(Proposal).where(Proposal.company_id == company_id).order_by(Proposal.updated_at.desc()).limit(8)
    ).all()
    recent = []
    for proposal in rows:
        stored = proposal.generation_input or {}
        client_name = stored.get("client_name") if isinstance(stored, dict) else None
        recent.append(
            RecentProposal(
                id=proposal.id,
                title=proposal.title,
                status=proposal.status,
                client_name=client_name if isinstance(client_name, str) else None,
                updated_at=proposal.updated_at,
            )
        )
    return recent


def _recent_months() -> list[str]:
    current = datetime.now(timezone.utc)
    year = current.year
    month = current.month
    keys = []
    for _ in range(12):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def _month_key(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return f"{value.year:04d}-{value.month:02d}"
