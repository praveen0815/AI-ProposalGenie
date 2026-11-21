"""Proposals, their sections, and immutable version snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, Uuid, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ApprovalAction, CostSource, ExportFormat, ProposalStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.client import Client
    from app.models.company import Company
    from app.models.user import User


class Proposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proposals"
    __table_args__ = (Index("ix_proposals_company_status", "company_id", "status"),)

    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("clients.id", ondelete="SET NULL"),
        index=True,
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(
            ProposalStatus,
            name="proposal_status",
            native_enum=False,
            length=32,
            create_constraint=True,
        ),
        nullable=False,
        default=ProposalStatus.DRAFT,
        server_default=ProposalStatus.DRAFT.value,
    )
    generation_input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    generation_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source_references: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    model_name: Mapped[str | None] = mapped_column(String(120))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_error: Mapped[str | None] = mapped_column(String(500))
    content_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    company: Mapped[Company] = relationship(back_populates="proposals")
    client: Mapped[Client | None] = relationship(back_populates="proposals")
    owner: Mapped[User | None] = relationship(back_populates="proposals", foreign_keys="Proposal.owner_id")
    sections: Mapped[list[ProposalSection]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProposalSection.position",
    )
    versions: Mapped[list[ProposalVersion]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ProposalSection(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proposal_sections"
    __table_args__ = (UniqueConstraint("proposal_id", "position", name="uq_proposal_sections_position"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    review_notes: Mapped[str | None] = mapped_column(Text)
    source_references: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    ai_body: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(16), nullable=False, default="user", server_default="user")

    proposal: Mapped[Proposal] = relationship(back_populates="sections")


class ProposalVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "proposal_versions"
    __table_args__ = (UniqueConstraint("proposal_id", "version_number", name="uq_proposal_versions_number"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    change_description: Mapped[str | None] = mapped_column(String(500))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    proposal: Mapped[Proposal] = relationship(back_populates="versions")
    created_by: Mapped[User | None] = relationship(
        back_populates="proposal_versions",
        foreign_keys="ProposalVersion.created_by_id",
    )


class ProposalCostItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A priced line. Estimated lines stay unapproved until a person confirms them."""

    __tablename__ = "proposal_cost_items"
    __table_args__ = (UniqueConstraint("proposal_id", "position", name="uq_proposal_cost_items_position"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="General", server_default="General")
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    duration: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=1, server_default=text("1"))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0, server_default=text("0"))
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False, default=0, server_default=text("0"))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source: Mapped[CostSource] = mapped_column(
        Enum(CostSource, name="cost_source", native_enum=False, length=32, create_constraint=True),
        nullable=False,
        default=CostSource.ESTIMATED,
        server_default=CostSource.ESTIMATED.value,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProposalApproval(UUIDPrimaryKeyMixin, Base):
    """Audit row for one approval action. Rows are not updated."""

    __tablename__ = "proposal_approvals"
    __table_args__ = (Index("ix_proposal_approvals_proposal_created", "proposal_id", "created_at"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[ApprovalAction] = mapped_column(
        Enum(ApprovalAction, name="approval_action", native_enum=False, length=32, create_constraint=True),
        nullable=False,
    )
    from_status: Mapped[str] = mapped_column(String(32), nullable=False)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProposalExport(UUIDPrimaryKeyMixin, Base):
    """One generated file. The storage key stays on the server."""

    __tablename__ = "proposal_exports"
    __table_args__ = (Index("ix_proposal_exports_proposal_created", "proposal_id", "created_at"),)

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format", native_enum=False, length=32, create_constraint=True),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(180), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
