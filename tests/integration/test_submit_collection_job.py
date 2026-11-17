"""Integration: submit-collection use case end-to-end with the policy gate.

Verifies the Phase 0 security property: the ONLY route toward acquisition
runs deterministic policy evaluation, records explicit state transitions,
and replays idempotently.
"""

from __future__ import annotations

from csip.application.dto.collection import SubmissionAccepted, SubmissionRejected
from csip.application.use_cases.submit_collection_job import build_default_submit_collection_job
from csip.domain.jobs.entities import JobState
from tests.in_memory import InMemoryRunRepository, InMemorySourceRegistry
from tests.support import approved_fixture_source


def command(source_id: str = "fixture:synthetic-supplier", key: str = "idem-1"):
    from csip.application.dto.collection import SubmitCollectionCommand

    return SubmitCollectionCommand(
        request_id="req-1",
        caller_id="operator:internal",
        source_id=source_id,
        purpose="refresh",
        page_family="product_detail",
        idempotency_key=key,
        max_pages=5,
    )


class TestApprovedSubmission:
    def test_approved_run_records_explicit_transitions(self) -> None:
        registry = InMemorySourceRegistry(
            sources={"fixture:synthetic-supplier": approved_fixture_source()}
        )
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)

        result = use_case.execute(command())
        assert isinstance(result, SubmissionAccepted)
        assert result.state == JobState.APPROVED.value
        assert result.replayed is False

        events = list(runs.get_run_events(result.run_id))
        assert [e.new_state for e in events] == [
            JobState.QUEUED, JobState.POLICY_CHECK, JobState.APPROVED,
        ]
        # Every transition carries a run ID and actor (audit attribution).
        assert all(e.run_id == result.run_id for e in events)
        assert all(e.actor == "system:policy_gate" for e in events)

    def test_approved_event_carries_authorization_reference(self) -> None:
        registry = InMemorySourceRegistry(
            sources={"fixture:synthetic-supplier": approved_fixture_source()}
        )
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)
        result = use_case.execute(command())
        approved_event = list(runs.get_run_events(result.run_id))[-1]
        assert approved_event.payload["method"] == "fixture"
        assert "basis=local_fixture" in approved_event.payload["authorization_reference"]


class TestPolicyDenial:
    def test_unregistered_source_rejected_with_blocked_state(self) -> None:
        registry = InMemorySourceRegistry()
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)

        result = use_case.execute(command(source_id="unknown:source"))
        assert isinstance(result, SubmissionRejected)
        assert result.reason == "source_not_registered"

        events = list(runs.get_run_events(result.run_id))
        assert events[-1].new_state is JobState.BLOCKED_BY_POLICY

    def test_expired_approval_routes_to_approval_required(self) -> None:
        from tests.support import utc

        expired = approved_fixture_source(expires=utc(2026, 11, 10))
        registry = InMemorySourceRegistry(sources={"fixture:synthetic-supplier": expired})
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)

        result = use_case.execute(command())
        assert isinstance(result, SubmissionRejected)
        assert result.reason == "approval_expired"
        assert list(runs.get_run_events(result.run_id))[-1].new_state is JobState.APPROVAL_REQUIRED


class TestIdempotentReplay:
    def test_same_key_returns_same_run_without_duplicate_transitions(self) -> None:
        registry = InMemorySourceRegistry(
            sources={"fixture:synthetic-supplier": approved_fixture_source()}
        )
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)

        first = use_case.execute(command())
        second = use_case.execute(command(key="idem-1"))

        assert isinstance(first, SubmissionAccepted)
        assert isinstance(second, SubmissionAccepted)
        assert second.run_id == first.run_id
        assert second.replayed is True
        assert len(runs.get_run_events(first.run_id)) == 3  # no duplicate transitions

    def test_different_keys_create_different_runs(self) -> None:
        registry = InMemorySourceRegistry(
            sources={"fixture:synthetic-supplier": approved_fixture_source()}
        )
        runs = InMemoryRunRepository()
        use_case = build_default_submit_collection_job(registry, runs)

        first = use_case.execute(command(key="k1"))
        second = use_case.execute(command(key="k2"))
        assert first.run_id != second.run_id
