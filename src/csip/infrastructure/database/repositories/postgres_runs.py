"""Postgres-backed run/event repository (blueprint 4.3).

Writes go through the csip_ingest role (the connection's URL); the
``job_events`` table is append-only at the database level (trigger), so
``append_event`` is INSERT-only by construction.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import insert, select, update
from sqlalchemy.orm import Session, sessionmaker

from csip.domain.jobs.entities import JobEvent, JobState
from csip.infrastructure.database.models.runs import JobEventRecord, RunRecord


class PostgresRunRepository:
    """RunRepositoryPort implementation over ``csip.runs`` / ``csip.job_events``."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

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
    ) -> None:
        with self._session_factory() as session:
            session.execute(
                insert(RunRecord).values(
                    run_id=run_id,
                    job_id=job_id,
                    request_id=request_id,
                    source_id=source_id,
                    caller_id=caller_id,
                    idempotency_key=idempotency_key,
                    page_family=page_family,
                    state=initial_state.value,
                )
            )
            session.commit()

    def find_run_id_by_idempotency_key(
        self, caller_id: str, idempotency_key: str
    ) -> str | None:
        with self._session_factory() as session:
            return session.scalar(
                select(RunRecord.run_id)
                .where(
                    RunRecord.caller_id == caller_id,
                    RunRecord.idempotency_key == idempotency_key,
                )
                .limit(1)
            )

    def get_job_id(self, run_id: str) -> str | None:
        with self._session_factory() as session:
            return session.scalar(
                select(RunRecord.job_id).where(RunRecord.run_id == run_id)
            )

    def append_event(self, event: JobEvent) -> None:
        with self._session_factory() as session:
            session.execute(
                insert(JobEventRecord).values(
                    run_id=event.run_id,
                    stage=event.stage,
                    previous_state=(
                        event.previous_state.value if event.previous_state else None
                    ),
                    new_state=event.new_state.value,
                    actor=event.actor,
                    occurred_at=event.occurred_at,
                    payload=dict(event.payload),
                )
            )
            # Current-state pointer on the run row (the events themselves are
            # immutable; this is the only mutable column).
            session.execute(
                update(RunRecord)
                .where(RunRecord.run_id == event.run_id)
                .values(state=event.new_state.value)
            )
            session.commit()

    def get_run_events(self, run_id: str) -> Sequence[JobEvent]:
        with self._session_factory() as session:
            records = session.scalars(
                select(JobEventRecord)
                .where(JobEventRecord.run_id == run_id)
                .order_by(JobEventRecord.id)
            ).all()
            return [
                JobEvent(
                    run_id=record.run_id,
                    stage=record.stage,
                    previous_state=(
                        JobState(record.previous_state)
                        if record.previous_state
                        else None
                    ),
                    new_state=JobState(record.new_state),
                    actor=record.actor,
                    occurred_at=record.occurred_at,
                    payload=dict(record.payload or {}),
                )
                for record in records
            ]

    def get_current_state(self, run_id: str) -> JobState | None:
        with self._session_factory() as session:
            value = session.scalar(
                select(RunRecord.state).where(RunRecord.run_id == run_id)
            )
            return JobState(value) if value else None
