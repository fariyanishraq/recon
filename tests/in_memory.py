"""In-memory repository implementations for tests (safe, non-persistent)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from csip.application.ports.repositories import SourceRegistryPort
from csip.domain.jobs.entities import JobEvent, JobState
from csip.domain.sources.entities import SourceProfile


@dataclass
class InMemorySourceRegistry(SourceRegistryPort):
    sources: dict[str, SourceProfile] = field(default_factory=dict)

    def get_source(self, source_id: str) -> SourceProfile | None:
        return self.sources.get(source_id)


@dataclass
class InMemoryRunRepository:
    """Minimal run/event store implementing RunRepositoryPort semantics."""

    events: list[JobEvent] = field(default_factory=list)
    idempotency_index: dict[tuple[str, str], str] = field(default_factory=dict)
    states: dict[str, JobState] = field(default_factory=dict)
    jobs: dict[str, str] = field(default_factory=dict)

    def create_run(
        self, *, run_id: str, job_id: str, request_id: str, source_id: str,
        caller_id: str, idempotency_key: str, page_family: str, initial_state: JobState,
    ) -> None:
        key = (caller_id, idempotency_key)
        if key in self.idempotency_index:
            raise AssertionError("idempotency collision: run already exists for key")
        self.idempotency_index[key] = run_id
        self.states[run_id] = initial_state
        self.jobs[run_id] = job_id

    def get_job_id(self, run_id: str) -> str | None:
        return self.jobs.get(run_id)

    def find_run_id_by_idempotency_key(
        self, caller_id: str, idempotency_key: str
    ) -> str | None:
        return self.idempotency_index.get((caller_id, idempotency_key))

    def append_event(self, event: JobEvent) -> None:
        self.events.append(event)
        self.states[event.run_id] = event.new_state

    def get_run_events(self, run_id: str) -> Sequence[JobEvent]:
        return [e for e in self.events if e.run_id == run_id]

    def get_current_state(self, run_id: str) -> JobState | None:
        return self.states.get(run_id)
