"""Tests: domain contract invariants."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from csip.domain.acquisition.entities import ArtifactType
from csip.domain.evidence.entities import EvidenceLocator, EvidenceType
from csip.domain.jobs.entities import CollectionRequest, JobState
from csip.domain.observations.entities import NormalizedCandidate, RawObservation, ValidationReport
from csip.domain.reviews.entities import ReviewStatus, ReviewTask
from csip.domain.sources.entities import SourceProfile, register_source
from csip.domain.sources.value_objects import (
    AccessBasis,
    AcquisitionMethod,
    AllowedScope,
    ApprovalStatus,
    PageFamily,
    RateLimits,
    host_matches,
)
from tests.support import approved_fixture_source, utc

NOW = utc(2026, 11, 17)


# -- SourceProfile invariants --------------------------------------------------


class TestSourceProfile:
    def test_enabled_source_requires_approved_status(self) -> None:
        with pytest.raises(ValueError, match="enabled source must have approved status"):
            SourceProfile(
                source_id="s1", name="S", canonical_domain="example.com", owner="o",
                access_basis="official_api", approved_methods=("documented_api",),
                allowed_scope=None,  # type: ignore[arg-type]
                rate_limits=RateLimits(), retention=None,  # type: ignore[arg-type]
                enabled=True,
            )

    def test_approved_requires_evidence(self) -> None:
        with pytest.raises(ValueError, match="approval evidence"):
            register_source(
                source_id="s1", name="S", canonical_domain="example.com", owner="o",
                access_basis=AccessBasis.OFFICIAL_API,
                approved_methods=(AcquisitionMethod.DOCUMENTED_API,),
                allowed_scope=AllowedScope(
                    allowed_hosts=("example.com",),
                    allowed_page_families=(PageFamily.PRODUCT_DETAIL,),
                ),
                approval_evidence=None,  # type: ignore[arg-type]
                approval_expires_at=utc(2027, 1, 1),
            )

    def test_currently_approved_respects_expiry(self) -> None:
        source = approved_fixture_source(expires=utc(2026, 11, 10))
        assert not source.is_currently_approved(NOW)

        source = approved_fixture_source(expires=utc(2027, 1, 1))
        assert source.is_currently_approved(NOW)

    def test_expiry_boundary_is_inclusive(self) -> None:
        source = approved_fixture_source(expires=utc(2026, 11, 17))
        # At exactly the expiry instant, approval is no longer current.
        assert not source.is_currently_approved(utc(2026, 11, 17))

    def test_naive_expiry_treated_as_utc(self) -> None:
        source = approved_fixture_source(expires=datetime(2027, 1, 1))
        assert source.is_currently_approved(NOW)

    def test_status_change_to_revoked_disables(self) -> None:
        source = approved_fixture_source().with_status(ApprovalStatus.REVOKED)
        assert not source.enabled
        assert source.approval_status is ApprovalStatus.REVOKED


class TestHostMatching:
    def test_subdomain_matches(self) -> None:
        assert host_matches("www.alibaba.com", ("alibaba.com",))
        assert host_matches("alibaba.com", ("alibaba.com",))
        assert host_matches("evilalibaba.com", ("alibaba.com",)) is False
        assert host_matches("", ("alibaba.com",)) is False


# -- CollectionRequest / events -------------------------------------------------


class TestCollectionRequest:
    def test_requires_idempotency_key(self) -> None:
        with pytest.raises(ValueError, match="idempotency"):
            CollectionRequest(
                request_id="r1", caller_id="operator:internal", source_id="s1",
                purpose="refresh", page_family="product_detail",
                idempotency_key="", requested_at=NOW,
            )

    def test_max_pages_bounded(self) -> None:
        with pytest.raises(ValueError, match="max_pages"):
            CollectionRequest(
                request_id="r1", caller_id="operator:internal", source_id="s1",
                purpose="refresh", page_family="product_detail", idempotency_key="k1",
                requested_at=NOW, max_pages=100_000,
            )


class TestJobStates:
    def test_terminal_and_exception_classification(self) -> None:
        assert JobState.COMPLETED.is_terminal
        assert JobState.BLOCKED_BY_POLICY.is_terminal
        assert not JobState.APPROVED.is_terminal
        assert JobState.PARSER_DRIFT.is_exception
        assert not JobState.ACQUIRING.is_exception


class TestReviewTask:
    def test_resolution_requires_reviewer_decision_and_reason(self) -> None:
        with pytest.raises(ValueError, match="reviewer"):
            ReviewTask(
                task_id="t1", run_id="run_x", reason="conflict",
                entity_kind="supplier", evidence_refs=(),
                proposed_action="merge", status=ReviewStatus.RESOLVED,
                before_values={},
            )


# -- Observations / evidence / candidates ---------------------------------------


def _evidence(field_key: str = "price") -> EvidenceLocator:
    return EvidenceLocator(
        field_key=field_key, evidence_type=EvidenceType.CSS_SELECTOR,
        locator=".price", snippet="US $0.85-1.20 / piece", page_family="product_detail",
    )


class TestRawObservation:
    def test_frozen_append_only(self) -> None:
        obs = RawObservation(
            observation_id="o1", run_id="run_x", source_id="s1", artifact_id="a1",
            field_key="price", raw_value="US $0.85 / piece", language="en",
            captured_at=datetime.now(UTC), evidence=_evidence(),
            parser_version="p1", schema_version="s1",
        )
        with pytest.raises(AttributeError):
            obs.raw_value = "changed"  # type: ignore[misc]

    def test_requires_parser_and_schema_versions(self) -> None:
        with pytest.raises(ValueError, match="parser"):
            RawObservation(
                observation_id="o1", run_id="run_x", source_id="s1", artifact_id="a1",
                field_key="price", raw_value="v", language="en",
                captured_at=datetime.now(UTC), evidence=_evidence(),
                parser_version="", schema_version="s1",
            )


class TestNormalizedCandidate:
    def test_populated_values_require_model_id(self) -> None:
        with pytest.raises(ValueError, match="model_id"):
            NormalizedCandidate(
                candidate_id="c1", run_id="run_x", observation_ids=("o1",),
                raw_values={"price": "US $0.85 / piece"},
                normalized_values={"price": "0.85 USD/piece"},
                original_language="en", evidence={"price": _evidence()},
            )

    def test_blank_raw_values_rejected(self) -> None:
        with pytest.raises(ValueError, match="blanked"):
            NormalizedCandidate(
                candidate_id="c1", run_id="run_x", observation_ids=("o1",),
                raw_values={"price": ""},
                normalized_values={"price": None},
                original_language="en", evidence={},
            )


class TestValidationReport:
    def test_hard_failures_cannot_pass(self) -> None:
        with pytest.raises(ValueError, match="cannot pass"):
            ValidationReport(
                candidate_id="c1", rule_set_version="r1", passed=True,
                hard_failures=("price missing",),
            )


class TestArtifacts:
    def test_artifact_requires_fingerprint(self) -> None:
        from csip.domain.acquisition.entities import AcquisitionArtifact

        with pytest.raises(ValueError, match="fingerprint"):
            AcquisitionArtifact(
                artifact_id="a1", source_id="s1", run_id="run_x",
                artifact_type=ArtifactType.FIXTURE, reference="product_detail.html",
                captured_at=NOW, content_fingerprint="", byte_size=0, storage_ref="x",
                retrieval_metadata={},
            )
