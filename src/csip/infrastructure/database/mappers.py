"""Row <-> domain mapping for the ``csip`` schema.

Domain entities are stdlib frozen dataclasses (ADR-002); mapping to/from
storage happens here at the infrastructure boundary only.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from csip.domain.sources.entities import SourceProfile
from csip.domain.sources.value_objects import (
    AccessBasis,
    AcquisitionMethod,
    AllowedScope,
    ApprovalEvidence,
    ApprovalStatus,
    PageFamily,
    RateLimits,
    RetentionPolicy,
    StopCondition,
)


def scope_to_json(scope: AllowedScope) -> dict[str, list[str]]:
    return {
        "allowed_hosts": list(scope.allowed_hosts),
        "allowed_page_families": [f.value for f in scope.allowed_page_families],
        "allowed_url_patterns": list(scope.allowed_url_patterns),
    }


def scope_from_json(data: Mapping[str, Any]) -> AllowedScope:
    return AllowedScope(
        allowed_hosts=tuple(data.get("allowed_hosts", ())),
        allowed_page_families=tuple(
            PageFamily(f) for f in data.get("allowed_page_families", ())
        ),
        allowed_url_patterns=tuple(data.get("allowed_url_patterns", ())),
    )


def rate_limits_to_json(limits: RateLimits) -> dict[str, int]:
    return {
        "max_requests_per_minute": limits.max_requests_per_minute,
        "max_concurrency": limits.max_concurrency,
        "max_pages_per_run": limits.max_pages_per_run,
    }


def rate_limits_from_json(data: Mapping[str, Any]) -> RateLimits:
    return RateLimits(
        max_requests_per_minute=int(data.get("max_requests_per_minute", 10)),
        max_concurrency=int(data.get("max_concurrency", 1)),
        max_pages_per_run=int(data.get("max_pages_per_run", 10)),
    )


def retention_to_json(retention: RetentionPolicy) -> dict[str, bool | int]:
    return {
        "retain_raw_days": retention.retain_raw_days,
        "retain_artifacts": retention.retain_artifacts,
        "redistribution_permitted": retention.redistribution_permitted,
    }


def retention_from_json(data: Mapping[str, Any]) -> RetentionPolicy:
    return RetentionPolicy(
        retain_raw_days=int(data.get("retain_raw_days", 90)),
        retain_artifacts=bool(data.get("retain_artifacts", False)),
        redistribution_permitted=bool(data.get("redistribution_permitted", False)),
    )


def approval_evidence_to_json(evidence: ApprovalEvidence) -> dict[str, str]:
    return {
        "reviewer": evidence.reviewer,
        "reviewed_at": evidence.reviewed_at.isoformat(),
        "reference": evidence.reference,
    }


def approval_evidence_from_json(data: Mapping[str, Any]) -> ApprovalEvidence:
    return ApprovalEvidence(
        reviewer=data["reviewer"],
        reviewed_at=datetime.fromisoformat(data["reviewed_at"]),
        reference=data["reference"],
    )


def profile_to_row(profile: SourceProfile) -> dict[str, Any]:
    """Map a SourceProfile onto the csip.sources column layout."""
    return {
        "source_id": profile.source_id,
        "name": profile.name,
        "canonical_domain": profile.canonical_domain,
        "owner": profile.owner,
        "access_basis": profile.access_basis.value,
        "approved_methods": [m.value for m in profile.approved_methods],
        "approval_status": profile.approval_status.value,
        "approval_evidence": (
            approval_evidence_to_json(profile.approval_evidence)
            if profile.approval_evidence is not None
            else None
        ),
        "approval_expires_at": profile.approval_expires_at,
        "enabled": profile.enabled,
        "allowed_scope": scope_to_json(profile.allowed_scope),
        "rate_limits": rate_limits_to_json(profile.rate_limits),
        "retention": retention_to_json(profile.retention),
        "stop_conditions": [c.value for c in profile.stop_conditions],
    }


def profile_from_row(row: Mapping[str, Any]) -> SourceProfile:
    evidence_data = row["approval_evidence"]
    return SourceProfile(
        source_id=row["source_id"],
        name=row["name"],
        canonical_domain=row["canonical_domain"],
        owner=row["owner"],
        access_basis=AccessBasis(row["access_basis"]),
        approved_methods=tuple(AcquisitionMethod(m) for m in row["approved_methods"]),
        allowed_scope=scope_from_json(row["allowed_scope"]),
        rate_limits=rate_limits_from_json(row["rate_limits"]),
        retention=retention_from_json(row["retention"]),
        stop_conditions=tuple(StopCondition(c) for c in row["stop_conditions"]),
        approval_status=ApprovalStatus(row["approval_status"]),
        approval_evidence=(
            approval_evidence_from_json(evidence_data)
            if evidence_data is not None
            else None
        ),
        approval_expires_at=_as_utc(row["approval_expires_at"]),
        enabled=bool(row["enabled"]),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
