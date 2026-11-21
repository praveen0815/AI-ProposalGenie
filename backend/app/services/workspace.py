"""Proposal editing, versions, costs, and approval."""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import audit
from app.core.untrusted import fence
from app.integrations.llm.errors import LLMError
from app.integrations.llm.provider import StructuredLanguageModel
from app.models.company import Company
from app.models.enums import ApprovalAction, CostSource, MembershipRole, ProposalStatus
from app.models.proposal import Proposal, ProposalApproval, ProposalCostItem, ProposalSection, ProposalVersion
from app.models.user import User
from app.proposals.approval import TransitionError, action_for_target, transition
from app.proposals.costing import line_amounts, sheet_totals
from app.repositories import memberships as membership_repository
from app.schemas.proposal import ProposalResponse, ProposalSectionResponse, SourceReference
from app.schemas.workspace import (
    ApprovalEventResponse,
    ApprovalRequest,
    CostLineResponse,
    CostSheetResponse,
    CostSheetWrite,
    DraftSave,
    RegenerateResponse,
    VersionComparison,
    VersionCreate,
    VersionDetail,
    VersionSummary,
)
from app.services import proposals as proposal_service

_SECTION_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {"body": {"type": "STRING"}},
    "required": ["body"],
}
_COST_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        "lines": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "category": {"type": "STRING"},
                    "quantity": {"type": "STRING"},
                    "unit": {"type": "STRING"},
                    "unit_price": {"type": "STRING"},
                    "duration": {"type": "STRING"},
                    "tax_percent": {"type": "STRING"},
                    "discount_percent": {"type": "STRING"},
                },
                "required": ["name", "category", "quantity", "unit", "unit_price", "duration", "tax_percent", "discount_percent"],
            },
        }
    },
    "required": ["lines"],
}


def save_draft(db: Session, actor: User, proposal_id: UUID, payload: DraftSave) -> ProposalResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    _reject_if_generating(proposal)
    if proposal.content_revision != payload.expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This proposal was updated somewhere else. Reload it before saving.",
        )
    _replace_sections(proposal, payload)
    flush_section_positions(db, proposal)
    proposal.title = payload.title
    stored = dict(proposal.generation_input or {})
    stored["project_title"] = payload.title
    proposal.generation_input = stored
    proposal.content_revision += 1
    db.commit()
    db.refresh(proposal)
    return proposal_service._detail(proposal)


def create_version(db: Session, actor: User, proposal_id: UUID, payload: VersionCreate) -> VersionDetail:
    proposal = proposal_service._editable(db, actor, proposal_id)
    version = _add_version(db, proposal, actor, payload.change_description)
    db.commit()
    db.refresh(version)
    return _version_detail(version)


def list_versions(db: Session, actor: User, proposal_id: UUID) -> list[VersionSummary]:
    proposal = proposal_service._visible(db, actor, proposal_id)
    rows = db.scalars(
        select(ProposalVersion).where(ProposalVersion.proposal_id == proposal.id).order_by(ProposalVersion.version_number.desc())
    ).all()
    return [_version_summary(row) for row in rows]


def get_version(db: Session, actor: User, proposal_id: UUID, version_id: UUID) -> VersionDetail:
    proposal = proposal_service._visible(db, actor, proposal_id)
    version = _version_for(db, proposal.id, version_id)
    return _version_detail(version)


def compare_versions(db: Session, actor: User, proposal_id: UUID, left_id: UUID, right_id: UUID) -> VersionComparison:
    proposal = proposal_service._visible(db, actor, proposal_id)
    left = _version_for(db, proposal.id, left_id)
    right = _version_for(db, proposal.id, right_id)
    left_sections = _snapshot_sections(left.snapshot)
    right_sections = _snapshot_sections(right.snapshot)
    changes = []
    left_by_title = {item["title"]: item["body"] for item in left_sections}
    right_by_title = {item["title"]: item["body"] for item in right_sections}
    for title in list(dict.fromkeys([*left_by_title, *right_by_title])):
        before = left_by_title.get(title)
        after = right_by_title.get(title)
        if before == after:
            continue
        if before is None:
            kind = "added"
        elif after is None:
            kind = "removed"
        else:
            kind = "changed"
        changes.append({"title": title, "change": kind, "left": before, "right": after})
    return VersionComparison(
        left_version_id=left.id,
        right_version_id=right.id,
        title_changed=left.snapshot.get("title") != right.snapshot.get("title"),
        changes=changes,
    )


def restore_version(db: Session, actor: User, proposal_id: UUID, version_id: UUID) -> ProposalResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    _reject_if_generating(proposal)
    chosen = _version_for(db, proposal.id, version_id)
    _add_version(db, proposal, actor, f"Saved before restoring version {chosen.version_number}")
    snapshot = chosen.snapshot
    proposal.title = str(snapshot.get("title") or proposal.title)
    proposal.sections.clear()
    db.flush()
    for index, item in enumerate(_snapshot_sections(snapshot), start=1):
        proposal.sections.append(
            ProposalSection(
                title=item["title"],
                body=item["body"],
                position=index,
                needs_review=bool(item.get("needs_review")),
                review_notes=item.get("review_notes"),
                source_references=item.get("source_references") or [],
                ai_body=item.get("ai_body"),
                origin=item.get("origin") or "user",
            )
        )
    proposal.content_revision += 1
    _add_version(db, proposal, actor, f"Restored version {chosen.version_number}")
    db.commit()
    db.refresh(proposal)
    return proposal_service._detail(proposal)


def regenerate_section(
    db: Session,
    actor: User,
    proposal_id: UUID,
    section_id: UUID,
    model: StructuredLanguageModel,
    *,
    confirm_overwrite: bool,
) -> RegenerateResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    _reject_if_generating(proposal)
    section = next((item for item in proposal.sections if item.id == section_id), None)
    if section is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")
    company = db.get(Company, proposal.company_id)
    prompt = (
        "Rewrite this proposal section. Begin with 'AI draft.' "
        "Do not invent prices, certifications, case studies, or client achievements. "
        "Keep the user's facts that are already in the section.\n\n"
        f"Section title: {section.title}\n"
        f"Current text:\n{fence('user_section', section.body)}\n"
        f"Company: {company.name if company else ''}\n"
        f"Request: {proposal.generation_input or {}}"
    )
    try:
        completion = model.generate_json(purpose="section_regenerate", prompt=prompt, schema=_SECTION_SCHEMA)
        body = str(json.loads(completion.text).get("body") or "").strip()
    except (LLMError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The section could not be regenerated") from exc
    if not body:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="The section could not be regenerated")
    if not body.lower().startswith("ai draft"):
        body = f"AI draft.\n\n{body}"
    previous = section.body
    user_edited = bool(previous.strip()) and previous.strip() != (section.ai_body or "").strip()
    if user_edited and not confirm_overwrite:
        return RegenerateResponse(applied=False, suggested_body=body, previous_body=previous, ai_body=section.ai_body, section=_section_response(section))
    section.ai_body = body
    section.body = body
    section.origin = "ai"
    proposal.content_revision += 1
    db.commit()
    db.refresh(proposal)
    refreshed = next(item for item in proposal.sections if item.id == section_id)
    return RegenerateResponse(
        applied=True,
        suggested_body=body,
        previous_body=previous,
        ai_body=body,
        section=_section_response(refreshed),
        proposal=proposal_service._detail(proposal),
    )


def get_costs(db: Session, actor: User, proposal_id: UUID) -> CostSheetResponse:
    proposal = proposal_service._visible(db, actor, proposal_id)
    return _cost_sheet(db, proposal.id)


def save_costs(db: Session, actor: User, proposal_id: UUID, payload: CostSheetWrite) -> CostSheetResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    existing = {
        item.id: item
        for item in db.scalars(select(ProposalCostItem).where(ProposalCostItem.proposal_id == proposal.id)).all()
    }
    kept: set[UUID] = set()
    for position, line in enumerate(payload.lines, start=1):
        source = line.source
        confirmed_by = None
        confirmed_at = None
        if line.id is not None and line.id in existing:
            current = existing[line.id]
            kept.add(line.id)
            if current.source == CostSource.CONFIRMED and source == CostSource.ESTIMATED:
                source = CostSource.CONFIRMED
            if source == CostSource.CONFIRMED:
                confirmed_by = current.confirmed_by_id or actor.id
                confirmed_at = current.confirmed_at or datetime.now(timezone.utc)
            current.name = line.name
            current.category = line.category
            current.quantity = line.quantity
            current.unit = line.unit
            current.unit_price = line.unit_price
            current.duration = line.duration
            current.tax_percent = line.tax_percent
            current.discount_percent = line.discount_percent
            current.currency = payload.currency
            current.source = source
            current.position = 1000 + position
            current.confirmed_by_id = confirmed_by
            current.confirmed_at = confirmed_at
        else:
            if source == CostSource.CONFIRMED:
                confirmed_by = actor.id
                confirmed_at = datetime.now(timezone.utc)
            db.add(
                ProposalCostItem(
                    proposal_id=proposal.id,
                    company_id=proposal.company_id,
                    name=line.name,
                    category=line.category,
                    quantity=line.quantity,
                    unit=line.unit,
                    unit_price=line.unit_price,
                    duration=line.duration,
                    tax_percent=line.tax_percent,
                    discount_percent=line.discount_percent,
                    currency=payload.currency,
                    source=source,
                    position=1000 + position,
                    confirmed_by_id=confirmed_by,
                    confirmed_at=confirmed_at,
                )
            )
    for item_id, item in existing.items():
        if item_id not in kept:
            db.delete(item)
    _reposition_costs(db, proposal.id)
    db.commit()
    return _cost_sheet(db, proposal.id)


def suggest_costs(db: Session, actor: User, proposal_id: UUID, model: StructuredLanguageModel, currency: str) -> CostSheetResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    code = currency.strip().upper()
    if len(code) != 3 or not code.isalpha():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Currency must be a three-letter code")
    prompt = (
        "Suggest cost lines for this proposal. These are estimates, not approved prices. "
        "Use the currency requested. Do not claim the prices are confirmed. "
        "Return quantities, units, unit prices, duration, tax percent, and discount percent as decimal strings.\n\n"
        f"Currency: {code}\n"
        f"Title: {proposal.title}\n"
        f"Request: {proposal.generation_input or {}}\n"
        f"Sections: {[{'title': section.title, 'body': section.body[:500]} for section in proposal.sections]}"
    )
    try:
        completion = model.generate_json(purpose="cost_suggestion", prompt=prompt, schema=_COST_SCHEMA)
        parsed = json.loads(completion.text)
    except (LLMError, json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cost suggestions could not be created") from exc
    lines = parsed.get("lines") if isinstance(parsed, dict) else None
    if not isinstance(lines, list) or not lines:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Cost suggestions could not be created")
    next_position = db.scalar(select(func.max(ProposalCostItem.position)).where(ProposalCostItem.proposal_id == proposal.id)) or 0
    for item in lines:
        if not isinstance(item, dict):
            continue
        try:
            quantity = Decimal(str(item.get("quantity")))
            unit_price = Decimal(str(item.get("unit_price")))
            duration = Decimal(str(item.get("duration") or "1"))
            tax_percent = Decimal(str(item.get("tax_percent") or "0"))
            discount_percent = Decimal(str(item.get("discount_percent") or "0"))
            name = str(item.get("name") or "").strip()
            unit = str(item.get("unit") or "").strip()
        except Exception:
            continue
        if not name or not unit or quantity <= 0 or unit_price < 0:
            continue
        next_position += 1
        db.add(
            ProposalCostItem(
                proposal_id=proposal.id,
                company_id=proposal.company_id,
                name=name[:200],
                category=str(item.get("category") or "General")[:80],
                quantity=quantity,
                unit=unit[:40],
                unit_price=unit_price,
                duration=duration,
                tax_percent=tax_percent,
                discount_percent=discount_percent,
                currency=code,
                source=CostSource.ESTIMATED,
                position=next_position,
            )
        )
    db.commit()
    return _cost_sheet(db, proposal.id)


def confirm_cost(db: Session, actor: User, proposal_id: UUID, item_id: UUID) -> CostSheetResponse:
    proposal = proposal_service._editable(db, actor, proposal_id)
    item = db.scalar(select(ProposalCostItem).where(ProposalCostItem.id == item_id, ProposalCostItem.proposal_id == proposal.id))
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cost line not found")
    item.source = CostSource.CONFIRMED
    item.confirmed_by_id = actor.id
    item.confirmed_at = datetime.now(timezone.utc)
    db.commit()
    return _cost_sheet(db, proposal.id)


def apply_approval(db: Session, actor: User, proposal_id: UUID, payload: ApprovalRequest) -> ProposalResponse:
    proposal = proposal_service._visible(db, actor, proposal_id)
    membership = membership_repository.get_for_user(db, proposal.company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    if payload.action == ApprovalAction.SUBMIT and membership.role == MembershipRole.MEMBER and proposal.owner_id != actor.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to change this proposal")
    try:
        target = transition(proposal.status, payload.action, membership.role, payload.comment)
    except TransitionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    previous = proposal.status
    proposal.status = target
    db.add(
        ProposalApproval(
            proposal_id=proposal.id,
            company_id=proposal.company_id,
            actor_id=actor.id,
            action=payload.action,
            from_status=previous.value,
            to_status=target.value,
            comment=payload.comment,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()
    db.refresh(proposal)
    audit("proposal.approval", actor_id=actor.id, company_id=proposal.company_id, resource_id=proposal.id)
    return proposal_service._detail(proposal)


def list_approvals(db: Session, actor: User, proposal_id: UUID) -> list[ApprovalEventResponse]:
    proposal = proposal_service._visible(db, actor, proposal_id)
    rows = db.scalars(
        select(ProposalApproval).where(ProposalApproval.proposal_id == proposal.id).order_by(ProposalApproval.created_at.asc())
    ).all()
    return [
        ApprovalEventResponse(
            id=row.id,
            action=row.action,
            from_status=ProposalStatus(row.from_status),
            to_status=ProposalStatus(row.to_status),
            comment=row.comment,
            actor_id=row.actor_id,
            created_at=row.created_at,
        )
        for row in rows
    ]


def apply_direct_status(db: Session, actor: User, proposal: Proposal, target: ProposalStatus) -> None:
    membership = membership_repository.get_for_user(db, proposal.company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    action = action_for_target(proposal.status, target)
    if action is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A proposal in {proposal.status.value} cannot move to {target.value}")
    try:
        transition(proposal.status, action, membership.role, None)
    except TransitionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    previous = proposal.status
    proposal.status = target
    db.add(
        ProposalApproval(
            proposal_id=proposal.id,
            company_id=proposal.company_id,
            actor_id=actor.id,
            action=action,
            from_status=previous.value,
            to_status=target.value,
            comment=None,
            created_at=datetime.now(timezone.utc),
        )
    )


def _replace_sections(proposal: Proposal, payload: DraftSave) -> None:
    current = {section.id: section for section in proposal.sections}
    seen: set[UUID] = set()
    for index, item in enumerate(payload.sections, start=1):
        if item.id is not None and item.id in current:
            section = current[item.id]
            seen.add(item.id)
            if section.body != item.body:
                section.origin = "custom" if section.origin == "custom" else "user"
            section.title = item.title
            section.body = item.body
            section.position = -(index)
        else:
            proposal.sections.append(
                ProposalSection(
                    title=item.title,
                    body=item.body,
                    position=-(index),
                    origin="custom",
                    source_references=[],
                )
            )
    for section_id, section in current.items():
        if section_id not in seen:
            proposal.sections.remove(section)


def flush_section_positions(db: Session, proposal: Proposal) -> None:
    db.flush()
    ordered = sorted(proposal.sections, key=lambda section: abs(section.position))
    for index, section in enumerate(ordered, start=1):
        section.position = index
    db.flush()


def _add_version(db: Session, proposal: Proposal, actor: User, description: str) -> ProposalVersion:
    number = db.scalar(select(func.max(ProposalVersion.version_number)).where(ProposalVersion.proposal_id == proposal.id)) or 0
    version = ProposalVersion(
        proposal_id=proposal.id,
        version_number=number + 1,
        created_by_id=actor.id,
        change_description=description[:500],
        snapshot={
            "title": proposal.title,
            "sections": [
                {
                    "title": section.title,
                    "body": section.body,
                    "position": section.position,
                    "needs_review": section.needs_review,
                    "review_notes": section.review_notes,
                    "source_references": section.source_references or [],
                    "ai_body": section.ai_body,
                    "origin": section.origin,
                }
                for section in sorted(proposal.sections, key=lambda item: item.position)
            ],
        },
    )
    db.add(version)
    db.flush()
    return version


def _version_for(db: Session, proposal_id: UUID, version_id: UUID) -> ProposalVersion:
    version = db.scalar(select(ProposalVersion).where(ProposalVersion.id == version_id, ProposalVersion.proposal_id == proposal_id))
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    return version


def _snapshot_sections(snapshot: dict) -> list[dict]:
    sections = snapshot.get("sections") if isinstance(snapshot, dict) else None
    if not isinstance(sections, list):
        return []
    normalized = []
    for item in sections:
        if not isinstance(item, dict) or "title" not in item:
            continue
        normalized.append(
            {
                "title": str(item.get("title") or "Section"),
                "body": str(item.get("body") or ""),
                "needs_review": bool(item.get("needs_review")),
                "review_notes": item.get("review_notes"),
                "source_references": item.get("source_references") or [],
                "ai_body": item.get("ai_body"),
                "origin": item.get("origin") or "user",
            }
        )
    return normalized


def _version_summary(version: ProposalVersion) -> VersionSummary:
    return VersionSummary(
        id=version.id,
        proposal_id=version.proposal_id,
        version_number=version.version_number,
        change_description=version.change_description,
        created_by_id=version.created_by_id,
        created_at=version.created_at,
    )


def _version_detail(version: ProposalVersion) -> VersionDetail:
    summary = _version_summary(version)
    return VersionDetail(**summary.model_dump(), snapshot=version.snapshot)


def _section_response(section: ProposalSection) -> ProposalSectionResponse:
    return ProposalSectionResponse(
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


def _cost_sheet(db: Session, proposal_id: UUID) -> CostSheetResponse:
    rows = db.scalars(select(ProposalCostItem).where(ProposalCostItem.proposal_id == proposal_id).order_by(ProposalCostItem.position.asc())).all()
    currencies = {row.currency for row in rows}
    if len(currencies) > 1:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cost lines use more than one currency")
    calculated = []
    responses = []
    for row in rows:
        amounts = line_amounts(Decimal(row.quantity), Decimal(row.unit_price), Decimal(row.duration), Decimal(row.tax_percent), Decimal(row.discount_percent))
        calculated.append(amounts)
        responses.append(
            CostLineResponse(
                id=row.id,
                name=row.name,
                category=row.category,
                quantity=Decimal(row.quantity),
                unit=row.unit,
                unit_price=Decimal(row.unit_price),
                duration=Decimal(row.duration),
                tax_percent=Decimal(row.tax_percent),
                discount_percent=Decimal(row.discount_percent),
                currency=row.currency,
                source=row.source,
                base=amounts["base"],
                discount=amounts["discount"],
                tax=amounts["tax"],
                subtotal=amounts["subtotal"],
                position=row.position,
                confirmed_at=row.confirmed_at,
            )
        )
    totals = sheet_totals(calculated)
    return CostSheetResponse(
        currency=next(iter(currencies), None),
        lines=responses,
        base=totals["base"],
        discount=totals["discount"],
        tax=totals["tax"],
        grand_total=totals["grand_total"],
        estimated_count=sum(1 for row in rows if row.source == CostSource.ESTIMATED),
        confirmed_count=sum(1 for row in rows if row.source == CostSource.CONFIRMED),
    )


def _reposition_costs(db: Session, proposal_id: UUID) -> None:
    db.flush()
    rows = db.scalars(select(ProposalCostItem).where(ProposalCostItem.proposal_id == proposal_id).order_by(ProposalCostItem.position.asc(), ProposalCostItem.created_at.asc())).all()
    for index, row in enumerate(rows, start=1):
        row.position = -index
    db.flush()
    for index, row in enumerate(rows, start=1):
        row.position = index


def _reject_if_generating(proposal: Proposal) -> None:
    if proposal.status == ProposalStatus.GENERATING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Wait until generation finishes before editing")
