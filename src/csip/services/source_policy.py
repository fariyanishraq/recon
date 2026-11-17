"""Deterministic source-policy evaluation (goals G1, FR-01, FR-03).

This is the single authorization gate for acquisition. It is pure
application logic: no network, no model, no side effects. Its output
(`PolicyDecision`) is the only thing that may produce an
`AcquisitionPlan`, and `AcquisitionPlan` is the only token acquisition
adapters accept. There is deliberately no path from a `CollectionRequest`
to acquisition that skips this evaluator.

Fail-closed by design: any uncertainty (missing profile, missing approval,
expired approval, missing access basis, method not approved, scope
mismatch, unknown caller) denies the request.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from csip.domain.acquisition.entities import AcquisitionPlan
from csip.domain.jobs.entities import CollectionRequest
from csip.domain.sources.entities import SourceProfile
from csip.domain.sources.value_objects import (
    AcquisitionMethod,
    ApprovalStatus,
    PageFamily,
    RateLimits,
    host_matches,
)


class PolicyDenialReason(StrEnum):
    """Stable, safe denial reasons. Never encode source-specific secrets."""

    SOURCE_NOT_REGISTERED = "source_not_registered"
    SOURCE_DISABLED = "source_disabled"
    SOURCE_NOT_APPROVED = "source_not_approved"
    APPROVAL_EXPIRED = "approval_expired"
    ACCESS_BASIS_MISSING = "access_basis_missing"
    METHOD_NOT_APPROVED = "method_not_approved"
    SCOPE_NOT_ALLOWED = "scope_not_allowed"
    CALLER_NOT_AUTHORIZED = "caller_not_authorized"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    SOURCE_REVOKED = "source_revoked"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Outcome of deterministic policy evaluation."""

    approved: bool
    reason: PolicyDenialReason | None
    plan: AcquisitionPlan | None
    warnings: tuple[str, ...] = ()

    @classmethod
    def denied(
        cls, reason: PolicyDenialReason, *, warnings: tuple[str, ...] = ()
    ) -> PolicyDecision:
        return cls(approved=False, reason=reason, plan=None, warnings=warnings)


# Callers permitted to run collection jobs. Phase 0 seed: the internal
# operator identity only. Real authentication/authorization enforcement
# (tokens, quotas, per-caller visibility) is enforced server-side at the
# API layer in Phase 1+; this check is defense-in-depth inside the gate.
AUTHORIZED_CALLERS = frozenset({"operator:internal"})


def evaluate_source_policy(
    request: CollectionRequest,
    profile: SourceProfile | None,
    *,
    now: datetime,
    run_id: str,
    method_override: AcquisitionMethod | None = None,
) -> PolicyDecision:
    """Evaluate whether a collection request may proceed, and produce a plan.

    ``method_override`` lets the acquisition router request the
    lowest-complexity approved method; when omitted, the lowest-complexity
    approved method is selected automatically (blueprint 2.3).
    """
    warnings: list[str] = []

    if request.caller_id not in AUTHORIZED_CALLERS:
        return PolicyDecision.denied(PolicyDenialReason.CALLER_NOT_AUTHORIZED)

    if profile is None:
        return PolicyDecision.denied(PolicyDenialReason.SOURCE_NOT_REGISTERED)

    if profile.approval_status in (ApprovalStatus.REVOKED, ApprovalStatus.SUSPENDED):
        return PolicyDecision.denied(PolicyDenialReason.SOURCE_REVOKED)

    if profile.approval_status != ApprovalStatus.APPROVED:
        return PolicyDecision.denied(PolicyDenialReason.SOURCE_NOT_APPROVED)

    if not profile.enabled:
        return PolicyDecision.denied(PolicyDenialReason.SOURCE_DISABLED)

    expires_at = profile.approval_expires_at
    if expires_at is None or _as_utc(now) >= _as_utc(expires_at):
        return PolicyDecision.denied(
            PolicyDenialReason.APPROVAL_EXPIRED,
            warnings=("approval expiry reached; collection paused until renewed",),
        )

    # Access basis must be explicitly recorded (never inferred from robots).
    if not profile.access_basis:
        return PolicyDecision.denied(PolicyDenialReason.ACCESS_BASIS_MISSING)
    method = method_override or _lowest_complexity_method(profile)
    if method is None or not profile.permits_method(method):
        return PolicyDecision.denied(PolicyDenialReason.METHOD_NOT_APPROVED)

    # Scope: the requested page family must be inside the approved scope.
    requested_family = PageFamily(request.page_family)
    if requested_family not in profile.allowed_scope.allowed_page_families:
        return PolicyDecision.denied(
            PolicyDenialReason.SCOPE_NOT_ALLOWED,
            warnings=(f"page family {request.page_family!r} is not in approved scope",),
        )

    # For network-reaching methods, the canonical domain must match scope
    # hosts. Fixture sources are exempt (no network side effects).
    if (
        method is not AcquisitionMethod.FIXTURE
        and profile.allowed_scope.allowed_hosts
        and not host_matches(profile.canonical_domain, profile.allowed_scope.allowed_hosts)
    ):
        return PolicyDecision.denied(
            PolicyDenialReason.SCOPE_NOT_ALLOWED,
            warnings=("canonical domain is not within approved hosts",),
        )

    bounded_limits, clamped = _bound_request(request, profile.rate_limits)
    if clamped:
        warnings.append(
            f"requested max_pages clamped to source ceiling {bounded_limits.max_pages_per_run}"
        )

    plan = AcquisitionPlan(
        source_id=profile.source_id,
        run_id=run_id,
        method=method,
        page_family=requested_family,
        scope_hosts=profile.allowed_scope.allowed_hosts,
        rate_limits=bounded_limits,
        stop_conditions=profile.stop_conditions,
        authorization_reference=(
            f"source={profile.source_id};basis={profile.access_basis.value};"
            "evidence_ref="
            f"{profile.approval_evidence.reference if profile.approval_evidence else 'none'}"
        ),
        approved_at=now,
        plan_expires_at=_as_utc(expires_at),
        warnings=tuple(warnings),
    )
    return PolicyDecision(approved=True, reason=None, plan=plan, warnings=tuple(warnings))


_METHOD_COMPLEXITY_ORDER: tuple[AcquisitionMethod, ...] = (
    AcquisitionMethod.FIXTURE,
    AcquisitionMethod.DOCUMENTED_API,
    AcquisitionMethod.PARTNER_FEED,
    AcquisitionMethod.SUPPLIER_EXPORT,
    AcquisitionMethod.AUTHORIZED_PORTAL,
    AcquisitionMethod.BROWSER_PAGES,
)


def _lowest_complexity_method(profile: SourceProfile) -> AcquisitionMethod | None:
    for method in _METHOD_COMPLEXITY_ORDER:
        if profile.permits_method(method):
            return method
    return None


def _bound_request(request: CollectionRequest, limits: RateLimits) -> tuple[RateLimits, bool]:
    """Clamp requested page volume to the source ceiling (bounded execution)."""
    clamped = request.max_pages > limits.max_pages_per_run
    if clamped:
        bounded = RateLimits(
            max_requests_per_minute=limits.max_requests_per_minute,
            max_concurrency=limits.max_concurrency,
            max_pages_per_run=limits.max_pages_per_run,
        )
        return bounded, True
    return limits, False


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
