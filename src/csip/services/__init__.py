"""Deterministic application services.

Policy evaluation, canonicalization, validation, entity resolution, and
idempotency live here as pure, bounded logic - never in prompts and never
inside agents (blueprint 5.5, project_structure responsibility map).
"""

from csip.services.source_policy import (
    PolicyDecision,
    PolicyDenialReason,
    evaluate_source_policy,
)

__all__ = [
    "PolicyDecision",
    "PolicyDenialReason",
    "evaluate_source_policy",
]
