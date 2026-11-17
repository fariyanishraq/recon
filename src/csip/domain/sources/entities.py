"""SourceProfile: the governance record that authorizes all acquisition."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from csip.domain.sources.value_objects import (
    AccessBasis,
    AcquisitionMethod,
    AllowedScope,
    ApprovalEvidence,
    ApprovalStatus,
    RateLimits,
    RetentionPolicy,
    StopCondition,
)


@dataclass(frozen=True, slots=True)
class SourceProfile:
    """A reviewed source record.

    An enabled source MUST carry: access basis, approved methods, allowed
    scope, rate limits, retention rules, owner, approval evidence, and an
    expiry/review date (goals G1). No acquisition may start for a source
    that fails to satisfy these invariants.
    """

    source_id: str
    name: str
    canonical_domain: str
    owner: str
    access_basis: AccessBasis
    approved_methods: tuple[AcquisitionMethod, ...]
    allowed_scope: AllowedScope
    rate_limits: RateLimits
    retention: RetentionPolicy
    stop_conditions: tuple[StopCondition, ...] = field(
        default_factory=lambda: tuple(StopCondition)
    )
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    approval_evidence: ApprovalEvidence | None = None
    approval_expires_at: datetime | None = None
    enabled: bool = False

    def __post_init__(self) -> None:
        if not self.source_id or not self.name or not self.owner:
            raise ValueError("source profile requires source_id, name, and owner")
        if self.enabled and self.approval_status != ApprovalStatus.APPROVED:
            raise ValueError("an enabled source must have approved status")
        if self.approval_status == ApprovalStatus.APPROVED and self.approval_evidence is None:
            raise ValueError("approved sources must record approval evidence")
        if self.approval_status == ApprovalStatus.APPROVED and self.approval_expires_at is None:
            raise ValueError("approved sources must record an approval expiry date")

    def is_currently_approved(self, now: datetime) -> bool:
        """Approval is current only when approved, enabled, and not expired."""
        if self.approval_status != ApprovalStatus.APPROVED or not self.enabled:
            return False
        if self.approval_expires_at is None:
            return False
        return now < _as_utc(self.approval_expires_at)

    def permits_method(self, method: AcquisitionMethod) -> bool:
        return method in self.approved_methods

    def with_status(self, status: ApprovalStatus | str) -> SourceProfile:
        coerced = ApprovalStatus(status)
        return replace(self, approval_status=coerced, enabled=(coerced == ApprovalStatus.APPROVED))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def register_source(
    *,
    source_id: str,
    name: str,
    canonical_domain: str,
    owner: str,
    access_basis: AccessBasis,
    approved_methods: Sequence[AcquisitionMethod],
    allowed_scope: AllowedScope,
    rate_limits: RateLimits | None = None,
    retention: RetentionPolicy | None = None,
    approval_evidence: ApprovalEvidence,
    approval_expires_at: datetime,
) -> SourceProfile:
    """Factory for an enabled, approved source profile (change-controlled)."""
    if not approved_methods:
        raise ValueError("an approved source must permit at least one method")
    return SourceProfile(
        source_id=source_id,
        name=name,
        canonical_domain=canonical_domain.lower().strip(),
        owner=owner,
        access_basis=access_basis,
        approved_methods=tuple(approved_methods),
        allowed_scope=allowed_scope,
        rate_limits=rate_limits or RateLimits(),
        retention=retention or RetentionPolicy(),
        approval_status=ApprovalStatus.APPROVED,
        approval_evidence=approval_evidence,
        approval_expires_at=approval_expires_at,
        enabled=True,
    )
