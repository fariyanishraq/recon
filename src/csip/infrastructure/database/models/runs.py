"""Run and job-event models (blueprint 4.3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from csip.infrastructure.database.models.sources import Base


class RunRecord(Base):
    __tablename__ = "runs"
    __table_args__ = (
        Index("uq_runs_caller_idempotency", "caller_id", "idempotency_key", unique=True),
        {"schema": "csip"},
    )

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    request_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    caller_id: Mapped[str] = mapped_column(Text, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    page_family: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class JobEventRecord(Base):
    __tablename__ = "job_events"
    __table_args__ = (
        Index("ix_job_events_run", "run_id"),
        {"schema": "csip"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("csip.runs.run_id"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[str | None] = mapped_column(String(48), nullable=True)
    new_state: Mapped[str] = mapped_column(String(48), nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
