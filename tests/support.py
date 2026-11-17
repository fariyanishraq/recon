"""Test support: shared builders for governed source fixtures."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from csip.domain.sources.entities import SourceProfile, register_source
from csip.domain.sources.value_objects import (
    AccessBasis,
    AcquisitionMethod,
    AllowedScope,
    ApprovalEvidence,
    PageFamily,
    RetentionPolicy,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def utc(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=UTC)


def approved_fixture_source(
    *,
    source_id: str = "fixture:synthetic-supplier",
    methods: tuple[AcquisitionMethod, ...] = (AcquisitionMethod.FIXTURE,),
    families: tuple[PageFamily, ...] = (PageFamily.PRODUCT_DETAIL,),
    expires: datetime | None = None,
    hosts: tuple[str, ...] = ("fixtures.internal",),
) -> SourceProfile:
    """A currently-approved source profile whose access basis is local fixtures."""
    return register_source(
        source_id=source_id,
        name="Synthetic Fixture Supplier",
        canonical_domain=hosts[0] if hosts else "fixtures.internal",
        owner="sourcing-ops",
        access_basis=AccessBasis.LOCAL_FIXTURE,
        approved_methods=methods,
        allowed_scope=AllowedScope(
            allowed_hosts=hosts,
            allowed_page_families=families,
        ),
        retention=RetentionPolicy(retain_raw_days=30, retain_artifacts=True),
        approval_evidence=ApprovalEvidence(
            reviewer="source-owner-review",
            reviewed_at=utc(2026, 11, 1),
            reference="synthetic-fixture-approval-2026-11",
        ),
        approval_expires_at=expires or utc(2027, 11, 1),
    )


def days_after(base: datetime, days: int) -> datetime:
    return base + timedelta(days=days)
