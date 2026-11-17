"""Acquisition contracts: AcquisitionPlan and AcquisitionArtifact."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from csip.domain.sources.value_objects import (
    AcquisitionMethod,
    PageFamily,
    RateLimits,
    StopCondition,
)


@dataclass(frozen=True, slots=True)
class AcquisitionPlan:
    """A policy-approved collection plan.

    Produced only by the deterministic policy evaluator. It is the sole
    authorization token that acquisition adapters may act on; a stage that
    never received a plan cannot acquire anything.
    """

    source_id: str
    run_id: str
    method: AcquisitionMethod
    page_family: PageFamily
    scope_hosts: tuple[str, ...]
    rate_limits: RateLimits
    stop_conditions: tuple[StopCondition, ...]
    authorization_reference: str
    approved_at: datetime
    plan_expires_at: datetime
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.authorization_reference:
            raise ValueError("an acquisition plan must carry its authorization reference")
        if self.approved_at > self.plan_expires_at:
            raise ValueError("plan expiry must not precede approval time")


@dataclass(frozen=True, slots=True)
class AcquisitionArtifact:
    """Captured source content plus retrieval metadata (goals FR-04)."""

    artifact_id: str
    source_id: str
    run_id: str
    artifact_type: ArtifactType
    reference: str  # canonical URL or fixture reference (non-secret)
    captured_at: datetime
    content_fingerprint: str  # sha256 hex of content
    byte_size: int
    storage_ref: str
    retrieval_metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.content_fingerprint:
            raise ValueError("artifacts must record a content fingerprint")
        if self.byte_size < 0:
            raise ValueError("byte_size must be >= 0")


class ArtifactType(StrEnum):
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"
    FIXTURE = "fixture"
