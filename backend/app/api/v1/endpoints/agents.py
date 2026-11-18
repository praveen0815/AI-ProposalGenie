"""Multi-agent workflow routes. These do not replace the single-step proposal API."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_embedding_service, get_proposal_model, get_vector_store
from app.integrations.llm.provider import StructuredLanguageModel
from app.models.user import User
from app.rag.embedding_service import EmbeddingService
from app.rag.vector_store import VectorStore
from app.schemas.agent import AgentEventResponse, AgentStatusResponse
from app.services import agent_workflow

router = APIRouter()


@router.post("/proposals/{proposal_id}/run", response_model=AgentStatusResponse)
def run_workflow(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    model: StructuredLanguageModel = Depends(get_proposal_model),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> AgentStatusResponse:
    return agent_workflow.run_workflow(db, actor, proposal_id, model, embeddings, store)


@router.get("/proposals/{proposal_id}/status", response_model=AgentStatusResponse)
def workflow_status(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AgentStatusResponse:
    return agent_workflow.status_for(db, actor, proposal_id)


@router.get("/proposals/{proposal_id}/history", response_model=list[AgentEventResponse])
def workflow_history(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[AgentEventResponse]:
    return agent_workflow.history_for(db, actor, proposal_id)


@router.post("/proposals/{proposal_id}/resume", response_model=AgentStatusResponse)
def resume_workflow(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    model: StructuredLanguageModel = Depends(get_proposal_model),
    embeddings: EmbeddingService = Depends(get_embedding_service),
    store: VectorStore = Depends(get_vector_store),
) -> AgentStatusResponse:
    return agent_workflow.resume_workflow(db, actor, proposal_id, model, embeddings, store)
