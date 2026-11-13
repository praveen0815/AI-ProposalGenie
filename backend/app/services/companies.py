"""Company profile and membership rules."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.enums import MembershipRole
from app.models.membership import CompanyMembership
from app.models.user import User
from app.repositories import companies as company_repository
from app.repositories import memberships as membership_repository
from app.repositories import users as user_repository
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    CompanyWrite,
    MemberCreate,
    MemberResponse,
    MemberRoleUpdate,
)

_PROFILE_FIELDS = (
    "name",
    "industry",
    "website",
    "description",
    "contact_email",
    "contact_phone",
    "address_line1",
    "address_line2",
    "city",
    "region",
    "postal_code",
    "country",
    "services",
    "expertise",
    "brand_tagline",
    "brand_voice",
    "brand_primary_color",
)


def _company_response(company: Company, role: MembershipRole) -> CompanyResponse:
    return CompanyResponse(
        id=company.id,
        name=company.name,
        industry=company.industry,
        website=company.website,
        description=company.description,
        contact_email=company.contact_email,
        contact_phone=company.contact_phone,
        address_line1=company.address_line1,
        address_line2=company.address_line2,
        city=company.city,
        region=company.region,
        postal_code=company.postal_code,
        country=company.country,
        services=list(company.services or []),
        expertise=list(company.expertise or []),
        brand_tagline=company.brand_tagline,
        brand_voice=company.brand_voice,
        brand_primary_color=company.brand_primary_color,
        role=role,
    )


def _member_response(membership: CompanyMembership, user: User) -> MemberResponse:
    return MemberResponse(
        user_id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership.role,
        created_at=membership.created_at,
    )


def _require_membership(db: Session, company_id: UUID, user: User) -> CompanyMembership:
    membership = membership_repository.get_for_user(db, company_id, user.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return membership


def _require_roles(membership: CompanyMembership, allowed: set[MembershipRole]) -> None:
    if membership.role not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action",
        )


def _can_assign(actor: MembershipRole, requested: MembershipRole) -> bool:
    if actor == MembershipRole.OWNER:
        return True
    return actor == MembershipRole.ADMIN and requested == MembershipRole.MEMBER


def create_company(db: Session, actor: User, payload: CompanyWrite) -> CompanyResponse:
    company = Company(**payload.model_dump())
    db.add(company)
    db.flush()
    membership = CompanyMembership(company_id=company.id, user_id=actor.id, role=MembershipRole.OWNER)
    db.add(membership)
    db.commit()
    db.refresh(company)
    return _company_response(company, MembershipRole.OWNER)


def list_companies(db: Session, actor: User) -> list[CompanyResponse]:
    return [_company_response(company, membership.role) for company, membership in company_repository.list_for_user(db, actor.id)]


def get_company(db: Session, actor: User, company_id: UUID) -> CompanyResponse:
    membership = _require_membership(db, company_id, actor)
    company = company_repository.get(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return _company_response(company, membership.role)


def update_company(db: Session, actor: User, company_id: UUID, payload: CompanyUpdate) -> CompanyResponse:
    membership = _require_membership(db, company_id, actor)
    _require_roles(membership, {MembershipRole.OWNER, MembershipRole.ADMIN})
    company = company_repository.get(db, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Company name is required")
    for field in _PROFILE_FIELDS:
        if field in changes:
            setattr(company, field, changes[field])
    company.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(company)
    return _company_response(company, membership.role)


def list_members(db: Session, actor: User, company_id: UUID) -> list[MemberResponse]:
    _require_membership(db, company_id, actor)
    return [_member_response(membership, user) for membership, user in membership_repository.list_for_company(db, company_id)]


def add_member(db: Session, actor: User, company_id: UUID, payload: MemberCreate) -> MemberResponse:
    actor_membership = _require_membership(db, company_id, actor)
    _require_roles(actor_membership, {MembershipRole.OWNER, MembershipRole.ADMIN})
    if not _can_assign(actor_membership.role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to assign that role",
        )

    target = user_repository.get_by_email(db, payload.email)
    if target is None or not target.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered user matches that email. Ask them to create an account first.",
        )
    if membership_repository.get_for_user(db, company_id, target.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="That user is already a member of this company")

    membership = CompanyMembership(company_id=company_id, user_id=target.id, role=payload.role)
    db.add(membership)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That user is already a member of this company",
        ) from exc
    db.refresh(membership)
    return _member_response(membership, target)


def update_member_role(
    db: Session,
    actor: User,
    company_id: UUID,
    user_id: UUID,
    payload: MemberRoleUpdate,
) -> MemberResponse:
    actor_membership = _require_membership(db, company_id, actor)
    _require_roles(actor_membership, {MembershipRole.OWNER})
    target_membership = membership_repository.get_for_user(db, company_id, user_id)
    if target_membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if target_membership.role == MembershipRole.OWNER and payload.role != MembershipRole.OWNER:
        if membership_repository.count_owners(db, company_id) <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The company must keep at least one owner",
            )

    target = user_repository.get_by_id(db, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    target_membership.role = payload.role
    target_membership.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(target_membership)
    return _member_response(target_membership, target)
