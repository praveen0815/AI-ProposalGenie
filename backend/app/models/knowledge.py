"""Company knowledge documents and their processing attempts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DocumentFileType, DocumentProcessingStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.user import User


def _status_column(constraint_name: str) -> Enum:
    return Enum(
        DocumentProcessingStatus,
        name=constraint_name,
        native_enum=False,
        length=32,
        create_constraint=True,
    )


class KnowledgeDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A file owned by one company. Extracted text is stored here and is not a list field."""

    __tablename__ = "knowledge_documents"
    __table_args__ = (Index("ix_knowledge_documents_company_created", "company_id", "created_at"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(200), nullable=False)
    storage_filename: Mapped[str] = mapped_column(String(80), nullable=False)
    file_type: Mapped[DocumentFileType] = mapped_column(
        Enum(
            DocumentFileType,
            name="ck_knowledge_documents_file_type",
            native_enum=False,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
    )
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(300), nullable=False)
    processing_status: Mapped[DocumentProcessingStatus] = mapped_column(
        _status_column("ck_knowledge_documents_processing_status"),
        nullable=False,
        default=DocumentProcessingStatus.UPLOADED,
        server_default=DocumentProcessingStatus.UPLOADED.value,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    character_count: Mapped[int | None] = mapped_column(Integer)
    page_count: Mapped[int | None] = mapped_column(Integer)
    processing_error: Mapped[str | None] = mapped_column(String(300))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="knowledge_documents")
    uploaded_by: Mapped[User | None] = relationship(back_populates="knowledge_documents")
    jobs: Mapped[list[DocumentProcessingJob]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class DocumentProcessingJob(UUIDPrimaryKeyMixin, Base):
    """One extraction attempt for a knowledge document."""

    __tablename__ = "document_processing_jobs"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[DocumentProcessingStatus] = mapped_column(
        _status_column("ck_document_processing_jobs_status"),
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[KnowledgeDocument] = relationship(back_populates="jobs")
