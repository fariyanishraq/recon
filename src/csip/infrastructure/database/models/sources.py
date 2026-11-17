"""Source registry model (change-controlled; goals G1)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for application-owned models."""


class SourceRecord(Base):
    __tablename__ = "sources"
    __table_args__ = {"schema": "csip"}  # noqa: RUF012 - SQLAlchemy API requires a dict

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_domain: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str] = mapped_column(Text, nullable=False)
    access_basis: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_methods: Mapped[list] = mapped_column(JSONB, nullable=False)
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False)
    approval_evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    approval_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    allowed_scope: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rate_limits: Mapped[dict] = mapped_column(JSONB, nullable=False)
    retention: Mapped[dict] = mapped_column(JSONB, nullable=False)
    stop_conditions: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
