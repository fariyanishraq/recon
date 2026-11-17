"""Submit a collection job through the source-policy gate (FR-01, FR-02).

This use case is the ONLY application path from a collection request toward
acquisition. It:

1. checks caller authorization (defense-in-depth; API auth is separate),
2. loads the source profile from the registry,
3. runs deterministic policy evaluation (``services.source_policy``),
4. on approval, creates a durable run and records transition events
   ``queued -> policy_check -> approved`` (blueprint 4.3),
5. on denial, records ``queued -> policy_check -> blocked_by_policy`` /
   ``approval_required`` and returns a safe rejection.

It never launches acquisition itself; the orchestrating workflow (Phase 1)
invokes adapters with the ``AcquisitionPlan`` returned here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from csip.application.dto.collection import (
    SubmissionAccepted,
    SubmissionRejected,
    SubmitCollectionCommand,
)
from csip.application.ports.repositories import RunRepositoryPort, SourceRegistryPort
from csip.domain.jobs.entities import CollectionRequest, JobEvent, JobState
from csip.services.source_policy import PolicyDenialReason, evaluate_source_policy
from csip.shared.errors import UnauthorizedCallerError, ValidationError
from csip.shared.identifiers import JobId, RunId, new_job_id, new_run_id

logger = logging.getLogger("csip.application.submit_collection_job")

ACTOR_SYSTEM = "system:policy_gate"


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SubmitCollectionJob:
    """Vendor-neutral use case: submit a governed collection job."""

    sources: SourceRegistryPort
    runs: RunRepositoryPort
    now_fn: Callable[[], datetime] = _utc_now

    def execute(self, command: SubmitCollectionCommand) -> SubmissionAccepted | SubmissionRejected:
        now = self.now_fn()

        request = _build_request(command, now)
        run_id, job_id, replayed = self._resolve_run(command, request)

        if replayed:
            # Idempotent replay: the run already exists; return its current
            # state without emitting duplicate transition events (FR-02,
            # blueprint 8.1). No side effects are repeated.
            state = self.runs.get_current_state(run_id)
            if state is None:
                state = JobState.QUEUED
            if state.is_terminal and state in _DENIAL_STATES:
                return SubmissionRejected(
                    run_id=run_id,
                    reason=_reason_for_denial_state(state),
                    source_id=request.source_id,
                    warnings=("replayed: original denial retained",),
                )
            return SubmissionAccepted(
                run_id=run_id,
                job_id=job_id,
                source_id=request.source_id,
                state=state.value,
                idempotency_key=request.idempotency_key,
                replayed=True,
            )

        self._transition(run_id, JobState.QUEUED, request)
        self._transition(run_id, JobState.POLICY_CHECK, request)

        profile = self.sources.get_source(request.source_id)
        decision = evaluate_source_policy(
            request, profile, now=now, run_id=run_id
        )

        if decision.approved and decision.plan is not None:
            assert decision.plan is not None  # narrows for type checkers
            self._transition(
                run_id,
                JobState.APPROVED,
                request,
                payload={
                    "method": decision.plan.method.value,
                    "authorization_reference": decision.plan.authorization_reference,
                    "max_pages": str(decision.plan.rate_limits.max_pages_per_run),
                },
                warnings=decision.warnings,
            )
            logger.info(
                "collection job approved",
                extra={"run_id": run_id, "source_id": request.source_id,
                       "method": decision.plan.method.value},
            )
            return SubmissionAccepted(
                run_id=run_id,
                job_id=job_id,
                source_id=request.source_id,
                state=JobState.APPROVED.value,
                idempotency_key=request.idempotency_key,
                replayed=replayed,
                warnings=decision.warnings,
            )

        terminal_state = (
            JobState.APPROVAL_REQUIRED
            if decision.reason in _APPROVAL_REASONS
            else JobState.BLOCKED_BY_POLICY
        )
        self._transition(
            run_id,
            terminal_state,
            request,
            payload={"reason": decision.reason.value if decision.reason else "unknown"},
            warnings=decision.warnings,
        )
        logger.warning(
            "collection job denied by policy",
            extra={"run_id": run_id, "source_id": request.source_id,
                   "reason": decision.reason.value if decision.reason else "unknown"},
        )
        return SubmissionRejected(
            run_id=run_id,
            reason=decision.reason.value if decision.reason else "unknown",
            source_id=request.source_id,
            warnings=decision.warnings,
        )

    # -- internals ----------------------------------------------------------

    def _resolve_run(
        self, command: SubmitCollectionCommand, request: CollectionRequest
    ) -> tuple[RunId, JobId, bool]:
        """Idempotent run creation: same key -> same logical run (FR-02)."""
        existing = self.runs.find_run_id_by_idempotency_key(
            request.caller_id, request.idempotency_key
        )
        if existing is not None:
            job_id = self.runs.get_job_id(existing) or new_job_id()
            return RunId(existing), JobId(job_id), True

        run_id = new_run_id()
        job_id = new_job_id()
        self.runs.create_run(
            run_id=run_id,
            job_id=job_id,
            request_id=request.request_id,
            source_id=request.source_id,
            caller_id=request.caller_id,
            idempotency_key=request.idempotency_key,
            page_family=request.page_family.value,
            initial_state=JobState.QUEUED,
        )
        return run_id, job_id, False

    def _transition(
        self,
        run_id: RunId,
        state: JobState,
        request: CollectionRequest,
        *,
        payload: dict[str, str] | None = None,
        warnings: tuple[str, ...] = (),
    ) -> None:
        previous = self.runs.get_current_state(run_id)
        event_payload: dict[str, str] = dict(payload or {})
        if warnings:
            event_payload["warnings"] = ";".join(warnings)
        event = JobEvent(
            run_id=run_id,
            stage="submit_collection",
            previous_state=previous,
            new_state=state,
            actor=ACTOR_SYSTEM,
            occurred_at=self.now_fn(),
            payload=event_payload,
        )
        self.runs.append_event(event)


_APPROVAL_REASONS = frozenset(
    {
        PolicyDenialReason.SOURCE_NOT_APPROVED,
        PolicyDenialReason.APPROVAL_EXPIRED,
        PolicyDenialReason.SOURCE_REVOKED,
    }
)

_DENIAL_STATES = frozenset({JobState.BLOCKED_BY_POLICY, JobState.APPROVAL_REQUIRED})


def _reason_for_denial_state(state: JobState) -> str:
    if state is JobState.APPROVAL_REQUIRED:
        return PolicyDenialReason.APPROVAL_EXPIRED.value
    return PolicyDenialReason.SOURCE_NOT_REGISTERED.value


def _build_request(command: SubmitCollectionCommand, now: datetime) -> CollectionRequest:
    from csip.domain.sources.value_objects import PageFamily

    if not command.caller_id:
        raise UnauthorizedCallerError("missing caller identity")
    if not command.idempotency_key:
        raise ValidationError("idempotency_key is required", details={"field": "idempotency_key"})
    try:
        page_family = PageFamily(command.page_family)
    except ValueError:
        raise ValidationError(
            f"unknown page family: {command.page_family!r}",
            details={"field": "page_family"},
        ) from None
    return CollectionRequest(
        request_id=command.request_id,
        caller_id=command.caller_id,
        source_id=command.source_id,
        purpose=command.purpose,
        page_family=page_family,
        idempotency_key=command.idempotency_key,
        requested_at=now,
        max_pages=command.max_pages,
    )


def build_default_submit_collection_job(
    sources: SourceRegistryPort, runs: RunRepositoryPort
) -> SubmitCollectionJob:
    """Wire the use case with the current system clock."""
    return SubmitCollectionJob(sources=sources, runs=runs, now_fn=_utc_now)
