"""Create, list, and download proposal exports."""

import re
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.audit import audit
from app.exports.document import BudgetGroup, BudgetRow, ProposalDocument
from app.exports.docx import render_docx
from app.exports.pdf import ExportError, render_pdf
from app.models.enums import ExportFormat, ProposalStatus
from app.models.proposal import Proposal, ProposalCostItem, ProposalExport
from app.models.user import User
from app.proposals.costing import line_amounts, money, sheet_totals
from app.schemas.export import ExportResponse
from app.services import proposals as proposal_service
from app.storage.base import StorageError
from app.storage.local import LocalDocumentStorage

_EXPORTABLE = {ProposalStatus.REVIEW, ProposalStatus.APPROVED, ProposalStatus.SENT}
_CONTENT_TYPES = {
    ExportFormat.PDF: "application/pdf",
    ExportFormat.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def create_export(
    db: Session,
    actor: User,
    proposal_id: UUID,
    export_format: ExportFormat,
    storage: LocalDocumentStorage,
) -> ExportResponse:
    proposal = _proposal(db, actor, proposal_id)
    if proposal.status not in _EXPORTABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only proposals in review, approved, or sent can be exported",
        )
    document = _document(db, proposal, storage)
    try:
        payload = render_pdf(document) if export_format == ExportFormat.PDF else render_docx(document)
    except ExportError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be exported",
        ) from exc
    export_id = uuid4()
    extension = export_format.value.lower()
    filename = _filename(proposal.title, extension)
    key = f"exports/{proposal.company_id}/{proposal.id}/{export_id}.{extension}"
    try:
        storage.save(key, payload)
    except StorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be exported",
        ) from exc
    row = ProposalExport(
        id=export_id,
        proposal_id=proposal.id,
        company_id=proposal.company_id,
        created_by_id=actor.id,
        format=export_format,
        filename=filename,
        content_type=_CONTENT_TYPES[export_format],
        storage_key=key,
        size_bytes=len(payload),
        content_revision=proposal.content_revision,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete(key)
        raise
    db.refresh(row)
    audit("proposal.export", actor_id=actor.id, company_id=proposal.company_id, resource_id=row.id)
    return _response(row, proposal.content_revision)


def list_exports(db: Session, actor: User, proposal_id: UUID) -> list[ExportResponse]:
    proposal = proposal_service._visible(db, actor, proposal_id)
    rows = db.scalars(
        select(ProposalExport).where(ProposalExport.proposal_id == proposal.id).order_by(ProposalExport.created_at.desc())
    ).all()
    return [_response(row, proposal.content_revision) for row in rows]


def read_export(db: Session, actor: User, proposal_id: UUID, export_id: UUID, storage: LocalDocumentStorage) -> tuple[ProposalExport, bytes]:
    proposal = proposal_service._visible(db, actor, proposal_id)
    row = db.scalar(select(ProposalExport).where(ProposalExport.id == export_id, ProposalExport.proposal_id == proposal.id))
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found")
    try:
        payload = storage.read(row.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Export not found") from exc
    return row, payload


def _proposal(db: Session, actor: User, proposal_id: UUID) -> Proposal:
    proposal = db.scalar(
        select(Proposal)
        .where(Proposal.id == proposal_id)
        .options(selectinload(Proposal.sections), selectinload(Proposal.client), selectinload(Proposal.company))
    )
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found")
    proposal_service._require_membership(db, proposal.company_id, actor)
    return proposal


def _document(db: Session, proposal: Proposal, storage: LocalDocumentStorage) -> ProposalDocument:
    company = proposal.company
    stored = proposal.generation_input or {}
    client_name = stored.get("client_name") if isinstance(stored, dict) else None
    if not isinstance(client_name, str) or not client_name.strip():
        client_name = proposal.client.name if proposal.client is not None else None
    lines: list[str] = []
    if client_name:
        lines.append(client_name)
    if proposal.client is not None:
        if proposal.client.industry:
            lines.append(proposal.client.industry)
        if proposal.client.contact_name:
            lines.append(proposal.client.contact_name)
        if proposal.client.contact_email:
            lines.append(proposal.client.contact_email)
    logo = _logo(company.logo_storage_key if company is not None else None, storage)
    created = datetime.now(timezone.utc)
    sections = tuple((section.title, section.body) for section in sorted(proposal.sections, key=lambda item: item.position))
    return ProposalDocument(
        company_name=company.name if company is not None else "Company",
        tagline=company.brand_tagline if company is not None else None,
        color=(company.brand_primary_color if company is not None and company.brand_primary_color else "#0E3A4D"),
        logo=logo,
        title=proposal.title,
        client_lines=tuple(lines),
        summary=proposal.summary,
        sections=sections,
        budgets=_budgets(db, proposal.id),
        created_label=created.strftime("%d %b %Y"),
    )


def _logo(key: str | None, storage: LocalDocumentStorage) -> bytes | None:
    if not key:
        return None
    try:
        return storage.read(key)
    except StorageError:
        return None


def _budgets(db: Session, proposal_id: UUID) -> tuple[BudgetGroup, ...]:
    rows = db.scalars(select(ProposalCostItem).where(ProposalCostItem.proposal_id == proposal_id).order_by(ProposalCostItem.position.asc())).all()
    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row.currency, []).append(row)
    groups: list[BudgetGroup] = []
    for currency, items in grouped.items():
        calculated = []
        rendered = []
        estimated = 0
        confirmed = 0
        for item in items:
            amounts = line_amounts(
                Decimal(item.quantity),
                Decimal(item.unit_price),
                Decimal(item.duration),
                Decimal(item.tax_percent),
                Decimal(item.discount_percent),
            )
            calculated.append(amounts)
            if item.source.value == "ESTIMATED":
                estimated += 1
            else:
                confirmed += 1
            rendered.append(
                BudgetRow(
                    name=item.name,
                    category=item.category,
                    quantity=f"{Decimal(item.quantity):.2f}",
                    unit=item.unit,
                    unit_price=f"{Decimal(item.unit_price):.2f}",
                    duration=f"{Decimal(item.duration):.2f}",
                    tax_percent=f"{Decimal(item.tax_percent):.2f}",
                    discount_percent=f"{Decimal(item.discount_percent):.2f}",
                    source=item.source.value,
                    subtotal=f"{amounts['subtotal']:.2f}",
                )
            )
        totals = sheet_totals(calculated)
        groups.append(
            BudgetGroup(
                currency=currency,
                rows=tuple(rendered),
                base=f"{money(totals['base']):.2f}",
                discount=f"{money(totals['discount']):.2f}",
                tax=f"{money(totals['tax']):.2f}",
                grand_total=f"{money(totals['grand_total']):.2f}",
                estimated_count=estimated,
                confirmed_count=confirmed,
            )
        )
    return tuple(groups)


def _filename(title: str, extension: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", title).strip("-._")
    cleaned = (cleaned[:80] or "proposal")
    return f"{cleaned}.{extension}"


def _response(row: ProposalExport, current_revision: int) -> ExportResponse:
    return ExportResponse(
        id=row.id,
        proposal_id=row.proposal_id,
        format=row.format,
        filename=row.filename,
        content_type=row.content_type,
        size_bytes=row.size_bytes,
        content_revision=row.content_revision,
        current_revision=current_revision,
        stale=row.content_revision != current_revision,
        created_at=row.created_at,
    )
