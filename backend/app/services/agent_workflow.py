"""Run, resume, and read the persisted multi-agent proposal workflow."""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.agents.errors import AgentWorkflowError
from app.agents.graph import AgentContext, build_graph, route_review
from app.agents.state import NODE_LABELS, NODE_ORDER, ProposalAgentState
from app.agents.tools import ClientResult, WorkflowTools
from app.core.config import get_settings
from app.integrations.llm.provider import StructuredLanguageModel
from app.models.company import Company
from app.models.enums import AgentRunStatus, ProposalStatus
from app.models.agent import AgentEvent, AgentRun
from app.models.proposal import Proposal, ProposalSection, ProposalVersion
from app.models.user import User
from app.rag.embedding_service import EmbeddingService
from app.rag.retriever import retrieve
from app.rag.vector_store import VectorStore
from app.schemas.agent import AgentEventResponse, AgentNodeStatus, AgentStatusResponse
from app.schemas.proposal import ProposalCreate
from app.services import proposals as proposal_service

logger = logging.getLogger("app.agents")
PROMPT_VERSION = "agent-v1"


def run_workflow(
    db: Session,
    actor: User,
    proposal_id: UUID,
    model: StructuredLanguageModel,
    embeddings: EmbeddingService,
    store: VectorStore,
) -> AgentStatusResponse:
    proposal = _proposal(db, actor, proposal_id)
    _ensure_profile(db, proposal)
    if _active_run(db, proposal.id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A workflow is already running for this proposal")
    state = _initial_state(db, proposal)
    run = AgentRun(
        proposal_id=proposal.id,
        company_id=proposal.company_id,
        created_by_id=actor.id,
        status=AgentRunStatus.RUNNING,
        current_node="requirement_analysis",
        iteration=0,
        state=state,
        started_at=datetime.now(timezone.utc),
    )
    proposal.status = ProposalStatus.GENERATING
    proposal.generation_error = None
    db.add(run)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A workflow is already running for this proposal") from exc
    db.refresh(run)
    _execute(db, actor, proposal, run, state, model, embeddings, store)
    return status_for(db, actor, proposal_id)


def resume_workflow(
    db: Session,
    actor: User,
    proposal_id: UUID,
    model: StructuredLanguageModel,
    embeddings: EmbeddingService,
    store: VectorStore,
) -> AgentStatusResponse:
    proposal = _proposal(db, actor, proposal_id)
    run = _latest_run(db, proposal.id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="There is no workflow to resume")
    if run.status == AgentRunStatus.COMPLETED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This workflow has already finished")
    events = _events_for_run(db, run.id)
    state = dict(run.state)
    state["resume_node"] = _resume_target(state, events)
    run.status = AgentRunStatus.RUNNING
    run.error = None
    run.finished_at = None
    proposal.status = ProposalStatus.GENERATING
    proposal.generation_error = None
    db.commit()
    _execute(db, actor, proposal, run, state, model, embeddings, store)
    return status_for(db, actor, proposal_id)


def status_for(db: Session, actor: User, proposal_id: UUID) -> AgentStatusResponse:
    proposal = proposal_service.get_proposal(db, actor, proposal_id)
    run = _latest_run(db, proposal.id)
    if run is None:
        return AgentStatusResponse(
            proposal_id=proposal.id,
            status="NOT_STARTED",
            nodes=[AgentNodeStatus(key=key, label=NODE_LABELS[key], status="pending") for key in NODE_ORDER],
        )
    return _status(run, _events_for_run(db, run.id))


def history_for(db: Session, actor: User, proposal_id: UUID) -> list[AgentEventResponse]:
    proposal = proposal_service.get_proposal(db, actor, proposal_id)
    events = db.scalars(
        select(AgentEvent)
        .where(AgentEvent.company_id == proposal.company_id)
        .join(AgentRun, AgentRun.id == AgentEvent.run_id)
        .where(AgentRun.proposal_id == proposal.id)
        .order_by(AgentEvent.created_at.asc())
        .limit(200)
    ).all()
    return [
        AgentEventResponse(
            id=event.id,
            run_id=event.run_id,
            node=event.node,
            phase=event.phase,
            message=event.message,
            payload=event.payload or {},
            created_at=event.created_at,
        )
        for event in events
    ]


def _execute(
    db: Session,
    actor: User,
    proposal: Proposal,
    run: AgentRun,
    state: dict,
    model: StructuredLanguageModel,
    embeddings: EmbeddingService,
    store: VectorStore,
) -> None:
    settings = get_settings()
    tools = WorkflowTools(
        company_id=str(proposal.company_id),
        client=_client_result(proposal, state),
        model=model,
        retrieve_knowledge=lambda query: retrieve(
            embeddings,
            store,
            company_id=proposal.company_id,
            query=query,
            top_k=settings.rag_top_k,
            similarity_threshold=settings.rag_similarity_threshold,
            document_ids=None,
        ),
        research_api_key=settings.research_api_key,
        research_base_url=settings.research_base_url,
    )

    def on_node(name: str, phase: str, snapshot: dict) -> None:
        run.current_node = name
        run.iteration = int(snapshot.get("iteration") or 0)
        if phase == "completed":
            run.state = _jsonable(snapshot)
        db.add(
            AgentEvent(
                run_id=run.id,
                company_id=run.company_id,
                node=name,
                phase=phase,
                message=_event_message(name, phase, snapshot),
                payload=_event_payload(name, phase, snapshot),
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    graph = build_graph(AgentContext(model=model, tools=tools, on_node=on_node))
    try:
        for _update in graph.stream(state, stream_mode="updates"):
            continue
    except Exception as exc:
        failure = _unwrap(exc)
        node = failure.node if failure is not None else run.current_node or "requirement_analysis"
        message = str(failure) if failure is not None else "The agent workflow could not be completed"
        _mark_failed(db, proposal, run, node, message)
        raise HTTPException(status_code=failure.status_code if failure is not None else 503, detail=message) from exc
    db.refresh(run)
    _save_proposal(db, actor, proposal, run, model.model_name)
    run.status = AgentRunStatus.COMPLETED
    run.error = None
    run.finished_at = datetime.now(timezone.utc)
    db.commit()


def _save_proposal(db: Session, actor: User, proposal: Proposal, run: AgentRun, model_name: str) -> None:
    current = db.scalar(select(Proposal).where(Proposal.id == proposal.id).options(selectinload(Proposal.sections)))
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    final = run.state
    sections = final.get("draft_sections") or []
    current.sections.clear()
    db.flush()
    for position, section in enumerate(sections, start=1):
        current.sections.append(
            ProposalSection(
                title=str(section["title"]),
                body=str(section["body"]),
                position=position,
                needs_review=bool(section.get("needs_review")),
                review_notes=section.get("review_notes") or None,
                source_references=section.get("source_references") or [],
            )
        )
    current.status = ProposalStatus.REVIEW
    current.model_name = model_name
    current.generated_at = datetime.now(timezone.utc)
    current.generation_error = None
    current.source_references = [
        {"document_id": item["document_id"], "filename": item["label"], "chunk_index": None}
        for item in final.get("research_sources") or []
        if item.get("kind") == "company_document" and item.get("document_id")
    ]
    current.generation_metadata = {
        "prompt_version": PROMPT_VERSION,
        "workflow": "langgraph",
        "run_id": str(run.id),
        "retrieval_status": final.get("retrieval_status"),
        "external_research_status": final.get("external_research_status"),
        "review_limit_reached": bool(final.get("review_limit_reached")),
    }
    version_number = db.scalar(select(ProposalVersion.version_number).where(ProposalVersion.proposal_id == current.id).order_by(ProposalVersion.version_number.desc()).limit(1))
    db.add(
        ProposalVersion(
            proposal_id=current.id,
            version_number=(version_number or 0) + 1,
            created_by_id=actor.id,
            snapshot={
                "title": current.title,
                "prompt_version": PROMPT_VERSION,
                "model_name": model_name,
                "sections": [{"title": section["title"], "needs_review": section.get("needs_review")} for section in sections],
            },
        )
    )


def _mark_failed(db: Session, proposal: Proposal, run: AgentRun, node: str, message: str) -> None:
    run.status = AgentRunStatus.FAILED
    run.current_node = node
    run.error = message[:500]
    run.finished_at = datetime.now(timezone.utc)
    proposal.status = ProposalStatus.DRAFT
    proposal.generation_error = message[:500]
    db.add(
        AgentEvent(
            run_id=run.id,
            company_id=run.company_id,
            node=node,
            phase="failed",
            message=message[:500],
            payload={},
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _initial_state(db: Session, proposal: Proposal) -> ProposalAgentState:
    try:
        payload = ProposalCreate.model_validate(proposal.generation_input or {})
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The saved proposal input is invalid") from exc
    company = db.get(Company, proposal.company_id)
    settings = get_settings()
    return {
        "proposal_id": str(proposal.id),
        "company_id": str(proposal.company_id),
        "client_requirements": payload.client_requirements,
        "generation_input": payload.model_dump(mode="json"),
        "company_profile": _company_facts(company) if company is not None else {},
        "client": {"name": payload.client_name, "industry": payload.client_industry},
        "requirement_summary": {},
        "retrieved_context": [],
        "retrieval_status": "empty",
        "research_findings": [],
        "research_sources": [],
        "external_research_status": "not_configured",
        "solution": {},
        "draft_sections": [],
        "review": {},
        "iteration": 0,
        "max_iterations": settings.agent_max_review_iterations,
        "execution_status": "running",
        "resume_node": "",
        "current_node": "",
        "error": "",
        "review_limit_reached": False,
    }


def _company_facts(company: Company) -> dict[str, object]:
    facts: dict[str, object] = {"name": company.name}
    for key in ("industry", "website", "description", "brand_tagline", "brand_voice"):
        value = getattr(company, key)
        if isinstance(value, str) and value.strip():
            facts[key] = value.strip()
    if company.services:
        facts["services"] = company.services
    if company.expertise:
        facts["expertise"] = company.expertise
    return facts


def _ensure_profile(db: Session, proposal: Proposal) -> None:
    company = db.get(Company, proposal.company_id)
    ready = company is not None and bool(
        (company.description or "").strip() or (company.industry or "").strip() or company.services
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add a description, industry, or services to the company profile before generating a proposal.",
        )


def _client_result(proposal: Proposal, state: dict) -> ClientResult:
    client = state.get("client") or {}
    website = proposal.client.website if proposal.client is not None else None
    return ClientResult(name=str(client.get("name") or "Client"), industry=client.get("industry"), website=website)


def _resume_target(state: dict, events: list[AgentEvent]) -> str:
    if not events:
        return "requirement_analysis"
    last = events[-1]
    if last.phase == "completed":
        if last.node == "quality_review":
            return route_review(state)  # type: ignore[arg-type]
        index = NODE_ORDER.index(last.node) if last.node in NODE_ORDER else 0
        return NODE_ORDER[min(index + 1, len(NODE_ORDER) - 1)]
    if last.node in NODE_ORDER:
        return last.node
    return "requirement_analysis"


def _status(run: AgentRun, events: list[AgentEvent]) -> AgentStatusResponse:
    completed = {event.node for event in events if event.phase == "completed"}
    nodes: list[AgentNodeStatus] = []
    for key in NODE_ORDER:
        if key in completed and not (run.status == AgentRunStatus.FAILED and run.current_node == key and events[-1].phase == "failed"):
            node_status = "completed"
        elif run.current_node == key and run.status == AgentRunStatus.RUNNING:
            node_status = "running"
        elif run.current_node == key and run.status == AgentRunStatus.FAILED:
            node_status = "failed"
        else:
            node_status = "pending"
        nodes.append(AgentNodeStatus(key=key, label=NODE_LABELS[key], status=node_status))
    state = run.state or {}
    return AgentStatusResponse(
        proposal_id=run.proposal_id,
        run_id=run.id,
        status=run.status.value,
        current_node=run.current_node or None,
        iteration=run.iteration,
        max_iterations=int(state.get("max_iterations") or 0),
        nodes=nodes,
        review=state.get("review") or {},
        sources=state.get("research_sources") or [],
        external_research_status=state.get("external_research_status"),
        review_limit_reached=bool(state.get("review_limit_reached")),
        error=run.error,
    )


def _event_message(name: str, phase: str, state: dict) -> str:
    label = NODE_LABELS.get(name, name)
    if phase == "started":
        return f"{label} started."
    if name == "quality_review" and phase == "completed":
        approved = (state.get("review") or {}).get("approved")
        return "Quality review accepted the draft." if approved else "Quality review requested corrections."
    if name == "research" and phase == "completed":
        return f"Research finished with external research {state.get('external_research_status', 'not_configured')}."
    return f"{label} finished."


def _event_payload(name: str, phase: str, state: dict) -> dict:
    if phase != "completed":
        return {}
    if name == "requirement_analysis":
        summary = state.get("requirement_summary") or {}
        return {"missing_information": summary.get("missing_information", [])}
    if name == "research":
        return {
            "external_research_status": state.get("external_research_status"),
            "source_count": len(state.get("research_sources") or []),
        }
    if name == "quality_review":
        review = state.get("review") or {}
        return {"approved": review.get("approved"), "corrections": review.get("corrections", [])}
    if name == "finalization":
        return {"section_count": len(state.get("draft_sections") or [])}
    return {}


def _proposal(db: Session, actor: User, proposal_id: UUID) -> Proposal:
    return proposal_service._editable(db, actor, proposal_id)


def _active_run(db: Session, proposal_id: UUID) -> AgentRun | None:
    return db.scalar(select(AgentRun).where(AgentRun.proposal_id == proposal_id, AgentRun.status == AgentRunStatus.RUNNING))


def _latest_run(db: Session, proposal_id: UUID) -> AgentRun | None:
    return db.scalar(select(AgentRun).where(AgentRun.proposal_id == proposal_id).order_by(AgentRun.started_at.desc()).limit(1))


def _events_for_run(db: Session, run_id: UUID) -> list[AgentEvent]:
    return list(db.scalars(select(AgentEvent).where(AgentEvent.run_id == run_id).order_by(AgentEvent.created_at.asc())).all())


def _unwrap(exc: Exception) -> AgentWorkflowError | None:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, AgentWorkflowError):
            return current
        current = current.__cause__ or current.__context__
    return None


def _jsonable(value: dict) -> dict:
    return json.loads(json.dumps(value, default=str))
