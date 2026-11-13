"""Company lookups scoped by membership."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.membership import CompanyMembership


def get(db: Session, company_id: UUID) -> Company | None:
    return db.get(Company, company_id)


def list_for_user(db: Session, user_id: UUID) -> list[tuple[Company, CompanyMembership]]:
    statement = (
        select(Company, CompanyMembership)
        .join(CompanyMembership, CompanyMembership.company_id == Company.id)
        .where(CompanyMembership.user_id == user_id)
        .order_by(Company.name.asc(), Company.created_at.asc())
    )
    return [(company, membership) for company, membership in db.execute(statement).all()]
