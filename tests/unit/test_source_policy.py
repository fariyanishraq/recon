"""Tests: the deterministic source-policy evaluator (goals G1, FR-01, FR-03).

These tests are the executable form of the Phase 0 exit gate: no
acquisition without a valid, current, approved source profile, and
fail-closed behavior on every uncertainty.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from csip.domain.acquisition.entities import AcquisitionPlan
from csip.domain.jobs.entities import CollectionRequest
from csip.domain.sources.value_objects import (
    AcquisitionMethod,
    AllowedScope,
    PageFamily,
)
from csip.services.source_policy import (
    PolicyDecision,
    PolicyDenialReason,
    evaluate_source_policy,
)
from tests.support import approved_fixture_source, utc

NOW = utc(2026, 11, 17)
CALLER = "operator:internal"


def request(
    *, source_id: str = "fixture:synthetic-supplier",
    page_family: str = "product_detail",
    caller: str = CALLER,
    max_pages: int = 5,
    key: str = "idem-1",
) -> CollectionRequest:
    return CollectionRequest(
        request_id="req-1",
        caller_id=caller,
        source_id=source_id,
        purpose="refresh",
        page_family=page_family,  # type: ignore[arg-type]
        idempotency_key=key,
        requested_at=datetime.now(UTC),
        max_pages=max_pages,
    )


class TestApprovalGate:
    def test_unregistered_source_denied(self) -> None:
        decision = evaluate_source_policy(
            request(source_id="unknown"), None, now=NOW, run_id="run_x"
        )
        assert decision.approved is False
        assert decision.reason is PolicyDenialReason.SOURCE_NOT_REGISTERED
        assert decision.plan is None

    def test_approved_source_produces_plan(self) -> None:
        source = approved_fixture_source()
        decision = evaluate_source_policy(request(), source, now=NOW, run_id="run_x")
        assert decision.approved is True
        plan = decision.plan
        assert isinstance(plan, AcquisitionPlan)
        assert plan.method is AcquisitionMethod.FIXTURE
        assert plan.page_family is PageFamily.PRODUCT_DETAIL
        assert plan.authorization_reference.startswith("source=fixture:synthetic-supplier")
        assert plan.rate_limits.max_pages_per_run >= 1

    def test_unapproved_status_denied(self) -> None:
        source = approved_fixture_source().with_status("pending_review")
        decision = evaluate_source_policy(request(), source, now=NOW, run_id="run_x")
        assert decision.reason is PolicyDenialReason.SOURCE_NOT_APPROVED

    def test_disabled_source_denied(self) -> None:
        import dataclasses

        source = approved_fixture_source()
        disabled = dataclasses.replace(source, enabled=False)
        decision = evaluate_source_policy(request(), disabled, now=NOW, run_id="run_x")
        assert decision.reason is PolicyDenialReason.SOURCE_DISABLED

    def test_expired_approval_denied(self) -> None:
        source = approved_fixture_source(expires=utc(2026, 11, 10))
        decision = evaluate_source_policy(request(), source, now=NOW, run_id="run_x")
        assert decision.reason is PolicyDenialReason.APPROVAL_EXPIRED
        assert any("expiry" in w for w in decision.warnings)

    def test_revoked_source_denied(self) -> None:
        source = approved_fixture_source().with_status("revoked")
        decision = evaluate_source_policy(request(), source, now=NOW, run_id="run_x")
        assert decision.reason is PolicyDenialReason.SOURCE_REVOKED

    def test_unauthorized_caller_denied(self) -> None:
        decision = evaluate_source_policy(
            request(caller="some-external-script"), approved_fixture_source(),
            now=NOW, run_id="run_x",
        )
        assert decision.reason is PolicyDenialReason.CALLER_NOT_AUTHORIZED


class TestMethodAndScope:
    def test_method_not_approved_denied(self) -> None:
        source = approved_fixture_source()  # fixture only
        decision = evaluate_source_policy(
            request(), source, now=NOW, run_id="run_x",
            method_override=AcquisitionMethod.BROWSER_PAGES,
        )
        assert decision.reason is PolicyDenialReason.METHOD_NOT_APPROVED

    def test_lowest_complexity_method_selected(self) -> None:
        source = approved_fixture_source(
            methods=(AcquisitionMethod.BROWSER_PAGES, AcquisitionMethod.DOCUMENTED_API),
        )
        decision = evaluate_source_policy(request(), source, now=NOW, run_id="run_x")
        assert decision.plan is not None
        assert decision.plan.method is AcquisitionMethod.DOCUMENTED_API

    def test_scope_mismatch_denied(self) -> None:
        source = approved_fixture_source(families=(PageFamily.PRODUCT_DETAIL,))
        decision = evaluate_source_policy(
            request(page_family="search_results"), source, now=NOW, run_id="run_x"
        )
        assert decision.reason is PolicyDenialReason.SCOPE_NOT_ALLOWED

    def test_domain_outside_approved_hosts_denied_for_network_methods(self) -> None:
        from csip.domain.sources.entities import register_source
        from csip.domain.sources.value_objects import (
            AccessBasis,
            ApprovalEvidence,
        )

        source = register_source(
            source_id="api:partner",
            name="Partner API",
            canonical_domain="scary-platform.example",
            owner="sourcing-ops",
            access_basis=AccessBasis.OFFICIAL_API,
            approved_methods=(AcquisitionMethod.DOCUMENTED_API,),
            allowed_scope=AllowedScope(
                allowed_hosts=("approved-partner.example",),
                allowed_page_families=(PageFamily.PRODUCT_DETAIL,),
            ),
            approval_evidence=ApprovalEvidence(
                reviewer="r", reviewed_at=utc(2026, 11, 1), reference="contract-1"
            ),
            approval_expires_at=utc(2027, 11, 1),
        )
        decision = evaluate_source_policy(
            request(source_id="api:partner"), source, now=NOW, run_id="run_x"
        )
        assert decision.reason is PolicyDenialReason.SCOPE_NOT_ALLOWED


class TestBoundedExecution:
    def test_requested_pages_clamped_to_ceiling(self) -> None:
        source = approved_fixture_source()
        decision = evaluate_source_policy(
            request(max_pages=999), source, now=NOW, run_id="run_x"
        )
        assert decision.approved is True
        assert decision.plan is not None
        assert decision.plan.rate_limits.max_pages_per_run == source.rate_limits.max_pages_per_run
        assert any("clamped" in w for w in decision.warnings)


class TestDecisionShape:
    def test_denial_carries_no_plan(self) -> None:
        decision = PolicyDecision.denied(PolicyDenialReason.SOURCE_NOT_REGISTERED)
        assert decision.plan is None
        assert decision.approved is False

    @pytest.mark.parametrize(
        "reason", [r for r in PolicyDenialReason], ids=[r.value for r in PolicyDenialReason]
    )
    def test_all_denial_reasons_are_stable_safe_strings(self, reason: PolicyDenialReason) -> None:
        assert reason.value.isidentifier() or "_" in reason.value
        assert "secret" not in reason.value
