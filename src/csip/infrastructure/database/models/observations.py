"""Raw observation and artifact models (goals FR-04, FR-06)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from csip.infrastructure.database.models.sources import Base


class ArtifactRecord(Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        # Duplicate-safe replay of the same artifact within a run.
        Index(
            "uq_artifacts_run_fingerprint",
            "run_id",
            "content_fingerprint",
            unique=True,
        ),
        {"schema": "csip"},
    )

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("csip.runs.run_id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reference: Mapped[str] = mapped_column(Text, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class RawObservationRecord(Base):
    __tablename__ = "raw_observations"
    __table_args__ = (
        # Idempotent replay: one observation per (run, artifact, field).
        Index(
            "uq_raw_obs_run_artifact_field",
            "run_id",
            "artifact_id",
            "field_key",
            unique=True,
        ),
        Index("ix_raw_obs_run", "run_id"),
        {"schema": "csip"},
    )

    observation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("csip.runs.run_id"), nullable=False
    )
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    artifact_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("csip.artifacts.artifact_id"), nullable=False
    )
    field_key: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_value: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
