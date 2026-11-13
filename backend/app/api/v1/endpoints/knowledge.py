"""Company knowledge document routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_document_storage
from app.core.config import get_settings
from app.models.user import User
from app.schemas.knowledge import DocumentResponse, DocumentStatusResponse
from app.services import documents as document_service
from app.storage.base import DocumentStorage

router = APIRouter()


@router.post("/documents/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    company_id: UUID = Query(),
    file: UploadFile = File(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_document_storage),
) -> DocumentResponse:
    data = await _read_upload(file)
    return document_service.upload_document(
        db,
        storage,
        current_user,
        company_id,
        file.filename,
        file.content_type,
        data,
    )


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(
    company_id: UUID = Query(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    return document_service.list_documents(db, current_user, company_id)


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    return document_service.get_document(db, current_user, document_id)


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DocumentStatusResponse:
    return document_service.get_status(db, current_user, document_id)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_document_storage),
) -> None:
    document_service.delete_document(db, storage, current_user, document_id)


@router.post("/documents/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    storage: DocumentStorage = Depends(get_document_storage),
) -> DocumentResponse:
    return document_service.reprocess_document(db, storage, current_user, document_id)


async def _read_upload(file: UploadFile) -> bytes:
    """Stop reading once the configured size limit is exceeded."""

    limit = get_settings().max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        block = await file.read(1024 * 1024)
        if not block:
            break
        total += len(block)
        if total > limit:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="File exceeds the upload size limit",
            )
        chunks.append(block)
    return b"".join(chunks)
