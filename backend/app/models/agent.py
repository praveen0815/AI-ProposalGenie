"""Persisted LangGraph workflow runs and their checkpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AgentRunStatus
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One execution of the proposal workflow. The state column is the checkpoint."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_company_proposal", "company_id", "proposal_id"),
        Index(
            "uq_agent_runs_one_active",
            "proposal_id",
            unique=True,
            postgresql_where=text("status = 'RUNNING'"),
        ),
    )

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
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(AgentRunStatus, name="agent_run_status", native_enum=False, length=32, create_constraint=True),
        nullable=False,
        default=AgentRunStatus.RUNNING,
        server_default=AgentRunStatus.RUNNING.value,
    )
    current_node: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="")
    iteration: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    error: Mapped[str | None] = mapped_column(String(500))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentEvent(UUIDPrimaryKeyMixin, Base):
    """A checkpoint event. History is read from this table, not from process memory."""

    __tablename__ = "agent_events"
    __table_args__ = (Index("ix_agent_events_run_created", "run_id", "created_at"),)

    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    node: Mapped[str] = mapped_column(String(64), nullable=False)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
