"""Company-scoped proposal queries."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.proposal import Proposal


def list_for_company(db: Session, company_id: UUID) -> list[Proposal]:
    statement = select(Proposal).where(Proposal.company_id == company_id).order_by(Proposal.created_at.asc())
    return list(db.scalars(statement))
