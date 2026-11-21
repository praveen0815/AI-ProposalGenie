"""Create, generate, and read company proposals."""

import json
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import audit
from app.core.config import get_settings
from app.core.untrusted import fence
from app.integrations.llm.errors import LLMAPIError, LLMResponseError, LLMTimeout
from app.integrations.llm.prompts import OUTLINE_SCHEMA, SECTIONS_SCHEMA, outline_prompt, sections_prompt
from app.integrations.llm.provider import StructuredLanguageModel
from app.integrations.llm.types import Completion, TokenUsage
from app.models.client import Client
from app.models.company import Company
from app.models.enums import MembershipRole, ProposalStatus
from app.models.membership import CompanyMembership
from app.models.proposal import Proposal, ProposalSection, ProposalVersion
from app.models.user import User
from app.proposals.sections import PROMPT_VERSION, SECTION_KEYS, SECTION_SPECS
from app.rag.embedding_service import EmbeddingService
from app.rag.retriever import RetrievedChunk, retrieve
from app.rag.vector_store import VectorStore
from app.repositories import memberships as membership_repository
from app.schemas.proposal import (
    ProposalCreate,
    ProposalResponse,
    ProposalSectionResponse,
    ProposalSummary,
    ProposalUpdate,
    SourceReference,
    TokenUsageResponse,
)

logger = logging.getLogger("app.proposals")

_TITLES = dict(SECTION_SPECS)
_ALWAYS_REVIEW = {"budget_and_cost"}
_MISSING_REVIEW = {
    "project_timeline": "timeline",
    "scope_of_work": "scope_of_work",
    "deliverables": "deliverables",
    "terms_and_conditions": "payment_terms",
}
_REVIEW_COPY = {
    "budget_and_cost": "A detailed cost breakdown was not provided.",
    "project_timeline": "Timeline was not provided.",
    "scope_of_work": "Scope of work was not provided.",
    "deliverables": "Deliverables were not provided.",
    "terms_and_conditions": "Payment terms were not provided.",
}


def list_proposals(db: Session, actor: User, company_id: UUID) -> list[ProposalSummary]:
    _require_membership(db, company_id, actor)
    rows = db.scalars(
        select(Proposal).where(Proposal.company_id == company_id).order_by(Proposal.created_at.desc())
    ).all()
    return [_summary(row) for row in rows]


def get_proposal(db: Session, actor: User, proposal_id: UUID) -> ProposalResponse:
    proposal = _visible(db, actor, proposal_id)
    return _detail(proposal)


def create_proposal(db: Session, actor: User, payload: ProposalCreate) -> ProposalResponse:
    membership = _require_membership(db, payload.company_id, actor)
    client = _find_or_create_client(db, membership.company_id, payload.client_name, payload.client_industry)
    proposal = Proposal(
        company_id=membership.company_id,
        client_id=client.id,
        owner_id=actor.id,
        title=payload.project_title,
        summary=_summary_text(payload),
        status=ProposalStatus.DRAFT,
        generation_input=payload.model_dump(mode="json"),
    )
    db.add(proposal)
    db.commit()
    db.refresh(proposal)
    audit("proposal.create", actor_id=actor.id, company_id=proposal.company_id, resource_id=proposal.id)
    return _detail(proposal)


def update_proposal(db: Session, actor: User, proposal_id: UUID, payload: ProposalUpdate) -> ProposalResponse:
    proposal = _editable(db, actor, proposal_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No changes were provided")
    if "title" in changes and changes["title"]:
        proposal.title = changes["title"]
        _input = dict(proposal.generation_input or {})
        _input["project_title"] = changes["title"]
        proposal.generation_input = _input
    if "summary" in changes:
        proposal.summary = changes["summary"]
    if "status" in changes and changes["status"] is not None:
        from app.services.workspace import apply_direct_status

        apply_direct_status(db, actor, proposal, changes["status"])
    db.commit()
    db.refresh(proposal)
    return _detail(proposal)


def delete_proposal(db: Session, actor: User, proposal_id: UUID) -> None:
    proposal = _editable(db, actor, proposal_id)
    db.delete(proposal)
    db.commit()


def generate_proposal(
    db: Session,
    actor: User,
    proposal_id: UUID,
    model: StructuredLanguageModel,
    embeddings: EmbeddingService,
    store: VectorStore,
) -> ProposalResponse:
    proposal = _editable(db, actor, proposal_id)
    company = db.get(Company, proposal.company_id)
    if company is None or not _profile_ready(company):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Add a description, industry, or services to the company profile before generating a proposal.",
        )
    try:
        payload = ProposalCreate.model_validate(proposal.generation_input or {})
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="The saved proposal input is invalid") from exc

    proposal.status = ProposalStatus.GENERATING
    proposal.generation_error = None
    db.commit()
    try:
        context, chunks, retrieval_status = _context(company, proposal, payload, embeddings, store)
        outline = model.generate_json(purpose="proposal_outline", prompt=outline_prompt(context), schema=OUTLINE_SCHEMA)
        outline_data = _parse_outline(_load_json(outline.text))
        drafted = model.generate_json(
            purpose="proposal_sections",
            prompt=sections_prompt(context, outline_data),
            schema=SECTIONS_SCHEMA,
        )
        sections = _parse_sections(_load_json(drafted.text), payload, chunks)
    except HTTPException:
        raise
    except LLMTimeout as exc:
        _fail(db, proposal, "The proposal could not be generated because the language model timed out")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=proposal.generation_error) from exc
    except LLMResponseError as exc:
        _fail(db, proposal, "The language model returned a proposal that could not be validated")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=proposal.generation_error) from exc
    except LLMAPIError as exc:
        _fail(db, proposal, "The language model could not generate the proposal")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=proposal.generation_error) from exc
    except Exception as exc:
        logger.exception("proposal generation failed")
        _fail(db, proposal, "The proposal could not be generated")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=proposal.generation_error) from exc

    _save_generation(db, proposal, actor, sections, chunks, retrieval_status, outline, drafted)
    db.commit()
    db.refresh(proposal)
    audit("proposal.generate", actor_id=actor.id, company_id=proposal.company_id, resource_id=proposal.id)
    return _detail(proposal)


def _context(
    company: Company,
    proposal: Proposal,
    payload: ProposalCreate,
    embeddings: EmbeddingService,
    store: VectorStore,
) -> tuple[dict[str, object], list[RetrievedChunk], str]:
    chunks: list[RetrievedChunk] = []
    retrieval_status = "empty"
    query = " ".join(
        part
        for part in (
            payload.project_title,
            payload.project_description,
            payload.client_requirements,
            payload.business_objectives,
            payload.scope_of_work,
        )
        if part
    )[:2000]
    try:
        settings = get_settings()
        chunks = retrieve(
            embeddings,
            store,
            company_id=proposal.company_id,
            query=query,
            top_k=settings.rag_top_k,
            similarity_threshold=settings.rag_similarity_threshold,
            document_ids=None,
        )
        retrieval_status = "available" if chunks else "empty"
    except Exception:
        logger.warning("proposal retrieval unavailable company_id=%s", proposal.company_id)
        retrieval_status = "unavailable"
        chunks = []

    provided = payload.model_dump(mode="json")
    missing = [key for key, value in provided.items() if key != "company_id" and not value]
    evidence = [
        {
            "document_id": str(chunk.document_id),
            "filename": chunk.filename,
            "page_number": chunk.page_number,
            "excerpt": fence("company_document", chunk.text[:1200]),
        }
        for chunk in chunks
    ]
    context = {
        "company_profile": _company_facts(company),
        "client": {
            "name": payload.client_name,
            "industry": payload.client_industry,
        },
        "request": {key: value for key, value in provided.items() if key != "company_id" and value},
        "missing_inputs": missing,
        "retrieved_documents": evidence,
        "retrieval_status": retrieval_status,
        "instruction": (
            "Use retrieved_documents and company_profile as verified evidence. "
            "Do not fill missing_inputs with invented facts."
        ),
    }
    return context, chunks, retrieval_status


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


def _profile_ready(company: Company) -> bool:
    has_description = bool(company.description and company.description.strip())
    has_industry = bool(company.industry and company.industry.strip())
    return has_description or has_industry or bool(company.services)


def _load_json(text: str) -> dict[str, object]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("The language model returned invalid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMResponseError("The language model returned invalid JSON")
    return parsed


def _parse_outline(payload: dict[str, object]) -> dict[str, object]:
    sections = payload.get("sections")
    if not isinstance(sections, list):
        raise LLMResponseError("The language model omitted the outline")
    keys = [_section_key(item) for item in sections]
    if tuple(keys) != SECTION_KEYS:
        raise LLMResponseError("The language model omitted a required section")
    return {"sections": [{"key": key, "title": _TITLES[key], "objective": _objective(item)} for key, item in zip(keys, sections, strict=True)]}


def _parse_sections(
    payload: dict[str, object],
    request: ProposalCreate,
    chunks: list[RetrievedChunk],
) -> list[dict[str, object]]:
    raw_sections = payload.get("sections")
    if not isinstance(raw_sections, list):
        raise LLMResponseError("The language model omitted the proposal sections")
    keys = [_section_key(item) for item in raw_sections]
    if tuple(keys) != SECTION_KEYS:
        raise LLMResponseError("The language model omitted a required section")
    allowed = {str(chunk.document_id): chunk for chunk in chunks}
    provided = request.model_dump()
    parsed: list[dict[str, object]] = []
    for key, item in zip(keys, raw_sections, strict=True):
        if not isinstance(item, dict):
            raise LLMResponseError("The language model returned an invalid section")
        body = str(item.get("body") or "").strip()
        if not body:
            raise LLMResponseError("The language model returned an empty section")
        if not body.lower().startswith("ai draft"):
            body = f"AI draft.\n\n{body}"
        notes = str(item.get("review_notes") or "").strip()
        needs_review = bool(item.get("needs_review"))
        if key in _ALWAYS_REVIEW or (key in _MISSING_REVIEW and not provided.get(_MISSING_REVIEW[key])):
            needs_review = True
            if key == "budget_and_cost" and request.budget_range:
                note = "Only the stated budget range is verified. A detailed cost breakdown was not provided."
            elif key == "budget_and_cost":
                note = "Budget range was not provided."
            else:
                note = _REVIEW_COPY[key]
            notes = f"{notes} {note}".strip() if notes else note
        references = _cited_sources(item.get("source_document_ids"), allowed)
        parsed.append(
            {
                "title": _TITLES[key],
                "body": body,
                "needs_review": needs_review,
                "review_notes": notes or None,
                "source_references": references,
            }
        )
    return parsed


def _cited_sources(raw_ids: object, allowed: dict[str, RetrievedChunk]) -> list[dict[str, object]]:
    if not isinstance(raw_ids, list):
        return []
    references: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw in raw_ids:
        document_id = str(raw)
        chunk = allowed.get(document_id)
        if chunk is None or document_id in seen:
            continue
        seen.add(document_id)
        references.append(
            {
                "document_id": document_id,
                "filename": chunk.filename,
                "chunk_index": chunk.chunk_index,
            }
        )
    return references


def _section_key(item: object) -> str:
    if not isinstance(item, dict) or not isinstance(item.get("key"), str):
        raise LLMResponseError("The language model returned an invalid section")
    return item["key"]


def _objective(item: object) -> str:
    if isinstance(item, dict) and isinstance(item.get("objective"), str) and item["objective"].strip():
        return item["objective"].strip()
    return "Draft this section from the verified context."


def _save_generation(
    db: Session,
    proposal: Proposal,
    actor: User,
    sections: list[dict[str, object]],
    chunks: list[RetrievedChunk],
    retrieval_status: str,
    outline: Completion,
    drafted: Completion,
) -> None:
    proposal.sections.clear()
    db.flush()
    for position, section in enumerate(sections, start=1):
        proposal.sections.append(
            ProposalSection(
                title=str(section["title"]),
                body=str(section["body"]),
                position=position,
                needs_review=bool(section["needs_review"]),
                review_notes=section["review_notes"] if isinstance(section["review_notes"], str) else None,
                source_references=section["source_references"],
                ai_body=str(section["body"]),
                origin="ai",
            )
        )
    proposal.content_revision = (proposal.content_revision or 0) + 1
    usage = _combined_usage(outline.usage, drafted.usage)
    proposal.status = ProposalStatus.REVIEW
    proposal.model_name = drafted.model
    proposal.generated_at = datetime.now(timezone.utc)
    proposal.generation_error = None
    proposal.source_references = [
        {
            "document_id": str(chunk.document_id),
            "filename": chunk.filename,
            "chunk_index": chunk.chunk_index,
        }
        for chunk in chunks
    ]
    proposal.generation_metadata = {
        "prompt_version": PROMPT_VERSION,
        "retrieval_status": retrieval_status,
        "usage": usage,
    }
    version_number = db.scalar(
        select(func.max(ProposalVersion.version_number)).where(ProposalVersion.proposal_id == proposal.id)
    )
    db.add(
        ProposalVersion(
            proposal_id=proposal.id,
            version_number=(version_number or 0) + 1,
            created_by_id=actor.id,
            change_description="Generated proposal",
            snapshot={
                "title": proposal.title,
                "prompt_version": PROMPT_VERSION,
                "model_name": drafted.model,
                "sections": [
                    {"title": section["title"], "body": section["body"], "needs_review": section["needs_review"]}
                    for section in sections
                ],
            },
        )
    )


def _combined_usage(first: TokenUsage | None, second: TokenUsage | None) -> dict[str, int | None]:
    def total(attr: str) -> int | None:
        values = [getattr(item, attr) for item in (first, second) if item is not None]
        numbers = [value for value in values if isinstance(value, int)]
        if not numbers:
            return None
        return sum(numbers)

    return {
        "prompt_tokens": total("prompt_tokens"),
        "completion_tokens": total("completion_tokens"),
        "total_tokens": total("total_tokens"),
    }


def _fail(db: Session, proposal: Proposal, message: str) -> None:
    proposal.status = ProposalStatus.DRAFT
    proposal.generation_error = message[:500]
    db.commit()


def _summary_text(payload: ProposalCreate) -> str:
    source = payload.project_description or payload.client_requirements
    return source[:280]


def _find_or_create_client(db: Session, company_id: UUID, name: str, industry: str | None) -> Client:
    existing = db.scalar(
        select(Client).where(Client.company_id == company_id, func.lower(Client.name) == name.lower()).limit(1)
    )
    if existing is not None:
        if industry and not existing.industry:
            existing.industry = industry
        return existing
    client = Client(company_id=company_id, name=name, industry=industry)
    db.add(client)
    db.flush()
    return client


def _require_membership(db: Session, company_id: UUID, actor: User) -> CompanyMembership:
    membership = membership_repository.get_for_user(db, company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return membership


def _visible(db: Session, actor: User, proposal_id: UUID) -> Proposal:
    proposal = db.scalar(
        select(Proposal)
        .where(Proposal.id == proposal_id)
        .options(selectinload(Proposal.sections), selectinload(Proposal.client))
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    _require_membership(db, proposal.company_id, actor)
    return proposal


def _editable(db: Session, actor: User, proposal_id: UUID) -> Proposal:
    proposal = _visible(db, actor, proposal_id)
    membership = _require_membership(db, proposal.company_id, actor)
    if membership.role not in {MembershipRole.OWNER, MembershipRole.ADMIN} and proposal.owner_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to change this proposal")
    return proposal


def _summary(proposal: Proposal) -> ProposalSummary:
    stored = proposal.generation_input or {}
    client_name = stored.get("client_name") if isinstance(stored, dict) else None
    return ProposalSummary(
        id=proposal.id,
        company_id=proposal.company_id,
        title=proposal.title,
        summary=proposal.summary,
        status=proposal.status,
        client_name=client_name if isinstance(client_name, str) else None,
        generation_error=proposal.generation_error,
        generated_at=proposal.generated_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )


def _detail(proposal: Proposal) -> ProposalResponse:
    metadata = proposal.generation_metadata or {}
    usage = metadata.get("usage") if isinstance(metadata, dict) else None
    stored = proposal.generation_input or {}
    client_name = stored.get("client_name") if isinstance(stored, dict) else None
    return ProposalResponse(
        id=proposal.id,
        company_id=proposal.company_id,
        client_id=proposal.client_id,
        title=proposal.title,
        summary=proposal.summary,
        status=proposal.status,
        client_name=client_name if isinstance(client_name, str) else None,
        model_name=proposal.model_name,
        prompt_version=metadata.get("prompt_version") if isinstance(metadata, dict) else None,
        retrieval_status=metadata.get("retrieval_status") if isinstance(metadata, dict) else None,
        token_usage=TokenUsageResponse.model_validate(usage) if isinstance(usage, dict) else None,
        generation_error=proposal.generation_error,
        generation_input=stored if isinstance(stored, dict) and stored else None,
        source_references=[SourceReference.model_validate(item) for item in proposal.source_references or []],
        content_revision=proposal.content_revision,
        sections=[
            ProposalSectionResponse(
                id=section.id,
                title=section.title,
                body=section.body,
                position=section.position,
                needs_review=section.needs_review,
                review_notes=section.review_notes,
                ai_body=section.ai_body,
                origin=section.origin,
                source_references=[SourceReference.model_validate(item) for item in section.source_references or []],
            )
            for section in proposal.sections
        ],
        generated_at=proposal.generated_at,
        created_at=proposal.created_at,
        updated_at=proposal.updated_at,
    )
