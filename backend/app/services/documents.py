"""Upload, extract, reprocess, and delete company knowledge documents."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import DocumentProcessingStatus, MembershipRole
from app.models.knowledge import DocumentProcessingJob, KnowledgeDocument
from app.models.membership import CompanyMembership
from app.models.user import User
from app.repositories import knowledge as knowledge_repository
from app.repositories import memberships as membership_repository
from app.schemas.knowledge import DocumentResponse, DocumentStatusResponse
from app.services.extraction import ExtractionFailed, RejectedUpload, extract_text, prepare_upload, stored_suffix
from app.storage.base import DocumentStorage, StorageError

logger = logging.getLogger(__name__)

_MANAGERS = {MembershipRole.OWNER, MembershipRole.ADMIN}


def upload_document(
    db: Session,
    storage: DocumentStorage,
    actor: User,
    company_id: UUID,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> DocumentResponse:
    _require_membership(db, company_id, actor)
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="File exceeds the upload size limit")
    if knowledge_repository.count_for_company(db, company_id) >= settings.max_documents_per_company:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This company has reached its document limit",
        )

    try:
        prepared = prepare_upload(filename, content_type, data)
    except RejectedUpload as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    document = KnowledgeDocument(
        company_id=company_id,
        uploaded_by_id=actor.id,
        original_filename=prepared.original_filename,
        storage_filename="pending",
        file_type=prepared.file_type,
        file_size=len(data),
        storage_key="pending",
        processing_status=DocumentProcessingStatus.UPLOADED,
    )
    db.add(document)
    db.flush()
    suffix = stored_suffix(prepared.file_type)
    document.storage_filename = f"{document.id}{suffix}"
    document.storage_key = f"{company_id}/{document.id}/{document.storage_filename}"

    try:
        storage.save(document.storage_key, data)
    except StorageError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    _process(db, document, data)
    try:
        db.commit()
    except Exception:
        storage.delete(document.storage_key)
        db.rollback()
        raise
    db.refresh(document)
    return _response(document)


def list_documents(db: Session, actor: User, company_id: UUID) -> list[DocumentResponse]:
    _require_membership(db, company_id, actor)
    return [_response(document) for document in knowledge_repository.list_for_company(db, company_id)]


def get_document(db: Session, actor: User, document_id: UUID) -> DocumentResponse:
    document, _membership = _visible_document(db, actor, document_id)
    return _response(document)


def get_status(db: Session, actor: User, document_id: UUID) -> DocumentStatusResponse:
    document, _membership = _visible_document(db, actor, document_id)
    return _status(document)


def delete_document(db: Session, storage: DocumentStorage, actor: User, document_id: UUID) -> None:
    document, membership = _visible_document(db, actor, document_id)
    _require_manage(membership, document, actor)
    try:
        storage.delete(document.storage_key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    db.delete(document)
    db.commit()


def reprocess_document(
    db: Session,
    storage: DocumentStorage,
    actor: User,
    document_id: UUID,
) -> DocumentResponse:
    document, membership = _visible_document(db, actor, document_id)
    _require_manage(membership, document, actor)
    if document.processing_status == DocumentProcessingStatus.PROCESSING:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This document is already being processed")
    try:
        data = storage.read(document.storage_key)
    except StorageError:
        _mark_failed(db, document, "The stored file is missing")
        db.commit()
        db.refresh(document)
        return _response(document)
    _process(db, document, data)
    db.commit()
    db.refresh(document)
    return _response(document)


def _process(db: Session, document: KnowledgeDocument, data: bytes) -> None:
    now = datetime.now(UTC)
    document.processing_status = DocumentProcessingStatus.PROCESSING
    document.processing_error = None
    document.updated_at = now
    job = DocumentProcessingJob(
        document_id=document.id,
        status=DocumentProcessingStatus.PROCESSING,
        started_at=now,
    )
    db.add(job)
    db.flush()

    try:
        extracted = extract_text(document.file_type, data)
    except ExtractionFailed as exc:
        message = _safe_message(str(exc))
        _apply_failure(document, job, message)
        logger.info("Document %s processing failed", document.id)
        return

    document.extracted_text = extracted.text
    document.character_count = len(extracted.text)
    document.page_count = extracted.page_count
    document.processing_status = DocumentProcessingStatus.COMPLETED
    document.processing_error = None
    document.processed_at = datetime.now(UTC)
    document.updated_at = document.processed_at
    job.status = DocumentProcessingStatus.COMPLETED
    job.error_message = None
    job.finished_at = document.processed_at
    logger.info("Document %s processing completed", document.id)


def _mark_failed(db: Session, document: KnowledgeDocument, message: str) -> None:
    now = datetime.now(UTC)
    job = DocumentProcessingJob(
        document_id=document.id,
        status=DocumentProcessingStatus.FAILED,
        error_message=message,
        started_at=now,
        finished_at=now,
    )
    db.add(job)
    _apply_failure(document, job, message)


def _apply_failure(document: KnowledgeDocument, job: DocumentProcessingJob, message: str) -> None:
    now = datetime.now(UTC)
    document.extracted_text = None
    document.character_count = None
    document.page_count = None
    document.processing_status = DocumentProcessingStatus.FAILED
    document.processing_error = message
    document.processed_at = now
    document.updated_at = now
    job.status = DocumentProcessingStatus.FAILED
    job.error_message = message
    job.finished_at = now


def _safe_message(message: str) -> str:
    cleaned = " ".join(message.split())
    return cleaned[:300] or "The file could not be read"


def _require_membership(db: Session, company_id: UUID, actor: User) -> CompanyMembership:
    membership = membership_repository.get_for_user(db, company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")
    return membership


def _visible_document(db: Session, actor: User, document_id: UUID) -> tuple[KnowledgeDocument, CompanyMembership]:
    document = knowledge_repository.get(db, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    membership = membership_repository.get_for_user(db, document.company_id, actor.id)
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document, membership


def _require_manage(membership: CompanyMembership, document: KnowledgeDocument, actor: User) -> None:
    if membership.role in _MANAGERS or document.uploaded_by_id == actor.id:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have permission to perform this action",
    )


def _response(document: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        company_id=document.company_id,
        uploaded_by_id=document.uploaded_by_id,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        processing_status=document.processing_status,
        character_count=document.character_count,
        page_count=document.page_count,
        processing_error=document.processing_error,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _status(document: KnowledgeDocument) -> DocumentStatusResponse:
    return DocumentStatusResponse(
        id=document.id,
        processing_status=document.processing_status,
        character_count=document.character_count,
        page_count=document.page_count,
        processing_error=document.processing_error,
        updated_at=document.updated_at,
    )
