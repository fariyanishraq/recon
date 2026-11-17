"""Command/query DTOs for application use cases.

These are plain frozen dataclasses: the API layer adapts them to FastAPI
request/response models, keeping the application layer vendor-neutral.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class SubmitCollectionCommand:
    """Input to the submit-collection use case."""

    request_id: str
    caller_id: str
    source_id: str
    purpose: str
    page_family: str
    idempotency_key: str
    max_pages: int = 5


@dataclass(frozen=True, slots=True)
class SubmissionAccepted:
    run_id: str
    job_id: str
    source_id: str
    state: str
    idempotency_key: str
    replayed: bool = False
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SubmissionRejected:
    run_id: str
    reason: str  # PolicyDenialReason value; safe, stable, non-sensitive
    source_id: str
    warnings: tuple[str, ...] = field(default_factory=tuple)
    detail: Mapping[str, str] | None = None
