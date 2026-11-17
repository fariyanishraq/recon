"""Postgres-backed source registry (read side of the change-controlled
registry, goals G1)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from csip.domain.sources.entities import SourceProfile
from csip.infrastructure.database.mappers import profile_from_row
from csip.infrastructure.database.models.sources import SourceRecord


class PostgresSourceRegistry:
    """SourceRegistryPort implementation over the ``csip.sources`` table."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_source(self, source_id: str) -> SourceProfile | None:
        with self._session_factory() as session:
            record = session.scalar(
                select(SourceRecord).where(SourceRecord.source_id == source_id)
            )
            if record is None:
                return None
            return profile_from_row(
                {
                    "source_id": record.source_id,
                    "name": record.name,
                    "canonical_domain": record.canonical_domain,
                    "owner": record.owner,
                    "access_basis": record.access_basis,
                    "approved_methods": record.approved_methods,
                    "approval_status": record.approval_status,
                    "approval_evidence": record.approval_evidence,
                    "approval_expires_at": record.approval_expires_at,
                    "enabled": record.enabled,
                    "allowed_scope": record.allowed_scope,
                    "rate_limits": record.rate_limits,
                    "retention": record.retention,
                    "stop_conditions": record.stop_conditions,
                }
            )
