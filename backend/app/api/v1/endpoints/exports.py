"""Proposal PDF and DOCX export routes."""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_document_storage
from app.models.enums import ExportFormat
from app.models.user import User
from app.schemas.export import ExportResponse
from app.services import exports as export_service
from app.storage.local import LocalDocumentStorage

router = APIRouter()


@router.post("/{proposal_id}/export/pdf", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
def export_pdf(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: LocalDocumentStorage = Depends(get_document_storage),
) -> ExportResponse:
    return export_service.create_export(db, actor, proposal_id, ExportFormat.PDF, storage)


@router.post("/{proposal_id}/export/docx", response_model=ExportResponse, status_code=status.HTTP_201_CREATED)
def export_docx(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: LocalDocumentStorage = Depends(get_document_storage),
) -> ExportResponse:
    return export_service.create_export(db, actor, proposal_id, ExportFormat.DOCX, storage)


@router.get("/{proposal_id}/exports", response_model=list[ExportResponse])
def list_exports(
    proposal_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> list[ExportResponse]:
    return export_service.list_exports(db, actor, proposal_id)


@router.get("/{proposal_id}/exports/{export_id}/download")
def download_export(
    proposal_id: UUID,
    export_id: UUID,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_user),
    storage: LocalDocumentStorage = Depends(get_document_storage),
) -> Response:
    row, payload = export_service.read_export(db, actor, proposal_id, export_id, storage)
    filename = row.filename.replace('"', "")
    encoded = quote(filename)
    return Response(
        content=payload,
        media_type=row.content_type,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded}"},
    )
