"""User accounts. Passwords are stored only as hashes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.knowledge import KnowledgeDocument
    from app.models.membership import CompanyMembership
    from app.models.proposal import Proposal, ProposalVersion


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    memberships: Mapped[list[CompanyMembership]] = relationship(back_populates="user")
    proposals: Mapped[list[Proposal]] = relationship(
        back_populates="owner",
        foreign_keys="Proposal.owner_id",
    )
    proposal_versions: Mapped[list[ProposalVersion]] = relationship(
        back_populates="created_by",
        foreign_keys="ProposalVersion.created_by_id",
    )
    knowledge_documents: Mapped[list[KnowledgeDocument]] = relationship(
        back_populates="uploaded_by",
        foreign_keys="KnowledgeDocument.uploaded_by_id",
    )
