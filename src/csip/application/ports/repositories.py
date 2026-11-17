"""Repository and registry ports."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from csip.domain.jobs.entities import JobEvent, JobState
from csip.domain.sources.entities import SourceProfile


@runtime_checkable
class SourceRegistryPort(Protocol):
    """Read access to the change-controlled source registry."""

    def get_source(self, source_id: str) -> SourceProfile | None:
        """Return the current profile, or None when unregistered."""
        ...


@runtime_checkable
class RunRepositoryPort(Protocol):
    """Persistence for run records and their state transitions."""

    def create_run(
        self,
        *,
        run_id: str,
        job_id: str,
        request_id: str,
        source_id: str,
        caller_id: str,
        idempotency_key: str,
        page_family: str,
        initial_state: JobState,
    ) -> None: ...

    def find_run_id_by_idempotency_key(
        self, caller_id: str, idempotency_key: str
    ) -> str | None:
        """Return the run created for this key, or None (idempotency, FR-02)."""
        ...

    def get_job_id(self, run_id: str) -> str | None: ...

    def append_event(self, event: JobEvent) -> None: ...

    def get_run_events(self, run_id: str) -> Sequence[JobEvent]: ...

    def get_current_state(self, run_id: str) -> JobState | None: ...


@runtime_checkable
class JobEventSinkPort(Protocol):
    """Append-only sink for job/audit events (secrets already redacted)."""

    def append(self, event: JobEvent) -> None: ...


def event_between(
    run_id: str,
    stage: str,
    previous: JobState | None,
    new: JobState,
    actor: str,
    payload: dict[str, str] | None = None,
    occurred_at: datetime | None = None,
) -> JobEvent:
    """Convenience factory for redacted transition events."""
    return JobEvent(
        run_id=run_id,
        stage=stage,
        previous_state=previous,
        new_state=new,
        actor=actor,
        occurred_at=occurred_at or datetime.now(),
        payload=payload or {},
    )
