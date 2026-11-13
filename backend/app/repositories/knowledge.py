"""Knowledge document lookups scoped to one company."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.knowledge import DocumentProcessingJob, KnowledgeDocument


def get(db: Session, document_id: UUID) -> KnowledgeDocument | None:
    return db.get(KnowledgeDocument, document_id)


def list_for_company(db: Session, company_id: UUID) -> list[KnowledgeDocument]:
    statement = (
        select(KnowledgeDocument)
        .where(KnowledgeDocument.company_id == company_id)
        .order_by(KnowledgeDocument.created_at.desc(), KnowledgeDocument.id.desc())
    )
    return list(db.scalars(statement).all())


def count_for_company(db: Session, company_id: UUID) -> int:
    statement = select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.company_id == company_id)
    return int(db.scalar(statement) or 0)


def count_jobs(db: Session, document_id: UUID) -> int:
    statement = (
        select(func.count()).select_from(DocumentProcessingJob).where(DocumentProcessingJob.document_id == document_id)
    )
    return int(db.scalar(statement) or 0)
