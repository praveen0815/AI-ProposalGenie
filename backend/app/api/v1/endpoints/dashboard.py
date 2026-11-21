"""Company analytics routes."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.dashboard import DashboardSummary, StatusDistribution, TrendResponse
from app.services import dashboard as dashboard_service

router = APIRouter()


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    company_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> DashboardSummary:
    return dashboard_service.summary(db, actor, company_id)


@router.get("/proposal-trends", response_model=TrendResponse)
def proposal_trends(
    company_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> TrendResponse:
    return dashboard_service.trends(db, actor, company_id)


@router.get("/status-distribution", response_model=StatusDistribution)
def status_distribution(
    company_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> StatusDistribution:
    return dashboard_service.status_distribution(db, actor, company_id)
