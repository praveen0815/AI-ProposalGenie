"""Company profile and membership endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.company import (
    CompanyResponse,
    CompanyUpdate,
    CompanyWrite,
    MemberCreate,
    MemberResponse,
    MemberRoleUpdate,
)
from app.services import companies as company_service

router = APIRouter()


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    payload: CompanyWrite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyResponse:
    return company_service.create_company(db, current_user, payload)


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyResponse]:
    return company_service.list_companies(db, current_user)


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyResponse:
    return company_service.get_company(db, current_user, company_id)


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: UUID,
    payload: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyResponse:
    return company_service.update_company(db, current_user, company_id, payload)


@router.get("/{company_id}/members", response_model=list[MemberResponse])
def list_members(
    company_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    return company_service.list_members(db, current_user, company_id)


@router.post("/{company_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    company_id: UUID,
    payload: MemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    """Add a person who already has an account. This release does not send email."""

    return company_service.add_member(db, current_user, company_id, payload)


@router.patch("/{company_id}/members/{user_id}", response_model=MemberResponse)
def update_member_role(
    company_id: UUID,
    user_id: UUID,
    payload: MemberRoleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemberResponse:
    return company_service.update_member_role(db, current_user, company_id, user_id, payload)
