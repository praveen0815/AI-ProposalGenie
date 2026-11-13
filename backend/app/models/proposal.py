"""Proposals, their sections, and immutable version snapshots."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProposalStatus
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
