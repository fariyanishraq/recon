"""Job and run contracts: CollectionRequest, job states, JobEvent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from csip.domain.sources.value_objects import AcquisitionMethod, PageFamily


class JobState(StrEnum):
    """Explicit lifecycle states (blueprint 4.3). Never a single boolean."""

    QUEUED = "queued"
    POLICY_CHECK = "policy_check"
    APPROVED = "approved"
    DISCOVERING = "discovering"
    ACQUIRING = "acquiring"
    EXTRACTING = "extracting"
    NORMALIZING = "normalizing"
    VALIDATING = "validating"
    RESOLVING = "resolving"
    PERSISTING = "persisting"
    COMPLETED = "completed"
    # Exception states
    BLOCKED_BY_POLICY = "blocked_by_policy"
    APPROVAL_REQUIRED = "approval_required"
    RATE_LIMITED = "rate_limited"
    SOURCE_UNAVAILABLE = "source_unavailable"
    PARSER_DRIFT = "parser_drift"
    MODEL_ERROR = "model_error"
    VALIDATION_FAILED = "validation_failed"
    REVIEW_REQUIRED = "review_required"
    CANCELLED = "cancelled"
    FAILED_TERMINAL = "failed_terminal"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATES

    @property
    def is_exception(self) -> bool:
        return self in _EXCEPTION_STATES


_TERMINAL_STATES = frozenset(
    {
        JobState.COMPLETED,
        JobState.BLOCKED_BY_POLICY,
        JobState.APPROVAL_REQUIRED,
        JobState.CANCELLED,
        JobState.FAILED_TERMINAL,
    }
)

_EXCEPTION_STATES = frozenset(
    {
        JobState.BLOCKED_BY_POLICY,
        JobState.APPROVAL_REQUIRED,
        JobState.RATE_LIMITED,
        JobState.SOURCE_UNAVAILABLE,
        JobState.PARSER_DRIFT,
        JobState.MODEL_ERROR,
        JobState.VALIDATION_FAILED,
        JobState.REVIEW_REQUIRED,
        JobState.CANCELLED,
        JobState.FAILED_TERMINAL,
    }
)


@dataclass(frozen=True, slots=True)
class CollectionRequest:
    """An authenticated caller's request to collect or refresh from a source."""

    request_id: str
    caller_id: str
    source_id: str
    purpose: str
    page_family: PageFamily
    idempotency_key: str
    requested_at: datetime
    max_pages: int = 5

    def __post_init__(self) -> None:
        if not self.request_id or not self.caller_id or not self.source_id:
            raise ValueError("collection request requires request_id, caller_id, and source_id")
        if not self.idempotency_key:
            raise ValueError("collection request requires an idempotency key")
        if self.max_pages < 1 or self.max_pages > 1000:
            raise ValueError("max_pages must be within [1, 1000]")


@dataclass(frozen=True, slots=True)
class JobEvent:
    """Append-only, redacted record of a state transition (blueprint 4.3)."""

    run_id: str
    stage: str
    previous_state: JobState | None
    new_state: JobState
    actor: str
    occurred_at: datetime
    payload: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.run_id or not self.actor:
            raise ValueError("job events require run_id and actor")


@dataclass(frozen=True, slots=True)
class AcquisitionMethodSelection:
    """The method recorded in the run when policy approves a plan."""

    method: AcquisitionMethod
    rationale: str

    def __post_init__(self) -> None:
        if not self.rationale:
            raise ValueError("method selection requires a rationale")
