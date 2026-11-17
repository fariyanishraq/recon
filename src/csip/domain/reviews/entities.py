"""Human review contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ReviewStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"


class ReviewDecision(StrEnum):
    ACCEPT = "accept"
    REJECT = "reject"
    MERGE = "merge"
    SPLIT = "split"
    ESCALATE = "escalate"


@dataclass(frozen=True, slots=True)
class ReviewTask:
    """A human-review task for ambiguity, conflict, or low evidence.

    Reviewer identity, timestamps, before/after values, and the decision
    reason are all audited (blueprint 6.1). Uncertain entity matches become
    review tasks; they are never destructively merged automatically.
    """

    task_id: str
    run_id: str
    reason: str
    entity_kind: str  # supplier | product | sku | field
    evidence_refs: tuple[str, ...]
    proposed_action: str
    status: ReviewStatus
    before_values: Mapping[str, str | None]
    after_values: Mapping[str, str | None] | None = None
    reviewer: str | None = None
    decided_at: datetime | None = None
    decision: ReviewDecision | None = None
    decision_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.task_id or not self.reason:
            raise ValueError("review tasks require task_id and reason")
        if self.status == ReviewStatus.RESOLVED:
            if self.reviewer is None or self.decision is None or self.decided_at is None:
                raise ValueError("resolved review tasks must record reviewer, decision, and time")
            if not self.decision_reason:
                raise ValueError("resolved review tasks must record a decision reason")
