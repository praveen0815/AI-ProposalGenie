"""Company membership lookups."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import MembershipRole
from app.models.membership import CompanyMembership
from app.models.user import User


def get_for_user(db: Session, company_id: UUID, user_id: UUID) -> CompanyMembership | None:
    statement = select(CompanyMembership).where(
        CompanyMembership.company_id == company_id,
        CompanyMembership.user_id == user_id,
    )
    return db.scalar(statement)


def list_for_company(db: Session, company_id: UUID) -> list[tuple[CompanyMembership, User]]:
    statement = (
        select(CompanyMembership, User)
        .join(User, User.id == CompanyMembership.user_id)
        .where(CompanyMembership.company_id == company_id)
        .order_by(User.full_name.asc(), User.email.asc())
    )
    return [(membership, user) for membership, user in db.execute(statement).all()]


def count_owners(db: Session, company_id: UUID) -> int:
    statement = (
        select(func.count())
        .select_from(CompanyMembership)
        .where(
            CompanyMembership.company_id == company_id,
            CompanyMembership.role == MembershipRole.OWNER,
        )
    )
    return int(db.scalar(statement) or 0)
