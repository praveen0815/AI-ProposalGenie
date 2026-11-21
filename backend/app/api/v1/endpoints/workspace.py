"""Editing, version, cost, and approval routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_proposal_model
from app.integrations.llm.provider import StructuredLanguageModel
from app.models.user import User
from app.schemas.proposal import ProposalResponse
from app.schemas.workspace import (
    ApprovalEventResponse,
    ApprovalRequest,
    CostSheetResponse,
    CostSheetWrite,
    DraftSave,
    RegenerateRequest,
    RegenerateResponse,
    VersionComparison,
    VersionCreate,
    VersionDetail,
    VersionSummary,
)
from app.services import workspace

router = APIRouter()


@router.put("/{proposal_id}/draft", response_model=ProposalResponse)
def save_draft(
    proposal_id: UUID,
    payload: DraftSave,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return workspace.save_draft(db, actor, proposal_id, payload)


@router.post("/{proposal_id}/sections/{section_id}/regenerate", response_model=RegenerateResponse)
def regenerate_section(
    proposal_id: UUID,
    section_id: UUID,
    payload: RegenerateRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    model: StructuredLanguageModel = Depends(get_proposal_model),
) -> RegenerateResponse:
    return workspace.regenerate_section(
        db,
        actor,
        proposal_id,
        section_id,
        model,
        confirm_overwrite=payload.confirm_overwrite,
    )


@router.get("/{proposal_id}/versions", response_model=list[VersionSummary])
def list_versions(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[VersionSummary]:
    return workspace.list_versions(db, actor, proposal_id)


@router.post("/{proposal_id}/versions", response_model=VersionDetail, status_code=status.HTTP_201_CREATED)
def create_version(
    proposal_id: UUID,
    payload: VersionCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> VersionDetail:
    return workspace.create_version(db, actor, proposal_id, payload)


@router.get("/{proposal_id}/versions/compare", response_model=VersionComparison)
def compare_versions(
    proposal_id: UUID,
    left_id: UUID,
    right_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> VersionComparison:
    return workspace.compare_versions(db, actor, proposal_id, left_id, right_id)


@router.get("/{proposal_id}/versions/{version_id}", response_model=VersionDetail)
def get_version(
    proposal_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> VersionDetail:
    return workspace.get_version(db, actor, proposal_id, version_id)


@router.post("/{proposal_id}/versions/{version_id}/restore", response_model=ProposalResponse)
def restore_version(
    proposal_id: UUID,
    version_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return workspace.restore_version(db, actor, proposal_id, version_id)


@router.get("/{proposal_id}/costs", response_model=CostSheetResponse)
def get_costs(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CostSheetResponse:
    return workspace.get_costs(db, actor, proposal_id)


@router.put("/{proposal_id}/costs", response_model=CostSheetResponse)
def save_costs(
    proposal_id: UUID,
    payload: CostSheetWrite,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CostSheetResponse:
    return workspace.save_costs(db, actor, proposal_id, payload)


@router.post("/{proposal_id}/costs/suggest", response_model=CostSheetResponse)
def suggest_costs(
    proposal_id: UUID,
    currency: str,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    model: StructuredLanguageModel = Depends(get_proposal_model),
) -> CostSheetResponse:
    return workspace.suggest_costs(db, actor, proposal_id, model, currency)


@router.post("/{proposal_id}/costs/items/{item_id}/confirm", response_model=CostSheetResponse)
def confirm_cost(
    proposal_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> CostSheetResponse:
    return workspace.confirm_cost(db, actor, proposal_id, item_id)


@router.get("/{proposal_id}/approval", response_model=list[ApprovalEventResponse])
def list_approvals(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[ApprovalEventResponse]:
    return workspace.list_approvals(db, actor, proposal_id)


@router.post("/{proposal_id}/approval", response_model=ProposalResponse)
def apply_approval(
    proposal_id: UUID,
    payload: ApprovalRequest,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return workspace.apply_approval(db, actor, proposal_id, payload)
