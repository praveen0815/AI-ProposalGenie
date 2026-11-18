"""Proposal collection and generation routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_embedding_service, get_proposal_model, get_vector_store
from app.integrations.llm.provider import StructuredLanguageModel
from app.models.user import User
from app.rag.embedding_service import EmbeddingService
from app.rag.vector_store import VectorStore
from app.schemas.proposal import ProposalCreate, ProposalResponse, ProposalSummary, ProposalUpdate
from app.services import proposals as proposal_service

router = APIRouter()


@router.post("", response_model=ProposalResponse, status_code=status.HTTP_201_CREATED)
def create_proposal(
    payload: ProposalCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return proposal_service.create_proposal(db, actor, payload)


@router.get("", response_model=list[ProposalSummary])
def list_proposals(
    company_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[ProposalSummary]:
    return proposal_service.list_proposals(db, actor, company_id)


@router.get("/{proposal_id}", response_model=ProposalResponse)
def get_proposal(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return proposal_service.get_proposal(db, actor, proposal_id)


@router.post("/{proposal_id}/generate", response_model=ProposalResponse)
def generate_proposal(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    model: StructuredLanguageModel = Depends(get_proposal_model),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> ProposalResponse:
    return proposal_service.generate_proposal(db, actor, proposal_id, model, embeddings, store)


@router.patch("/{proposal_id}", response_model=ProposalResponse)
def update_proposal(
    proposal_id: UUID,
    payload: ProposalUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> ProposalResponse:
    return proposal_service.update_proposal(db, actor, proposal_id, payload)


@router.delete("/{proposal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proposal(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> None:
    proposal_service.delete_proposal(db, actor, proposal_id)
