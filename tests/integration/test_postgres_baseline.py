"""Integration tests against the live Supabase/Postgres ``csip`` schema.

These tests exercise the real database (roles, triggers, indexes). They are
skipped when the DB URLs are absent or the database is unreachable, keeping
the in-memory suite green everywhere.

Append-only discipline note: job_events rows can never be deleted (by
design), so every test run uses fresh unique ids and leaves its audit trail
behind.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy.exc
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from csip.application.dto.collection import SubmitCollectionCommand
from csip.application.ports.repositories import event_between
from csip.application.use_cases.submit_collection_job import (
    build_default_submit_collection_job,
)
from csip.domain.jobs.entities import JobState
from csip.domain.sources.entities import SourceProfile, register_source
from csip.domain.sources.value_objects import (
    AccessBasis,
    AcquisitionMethod,
    AllowedScope,
    ApprovalEvidence,
    PageFamily,
    RetentionPolicy,
)
from csip.infrastructure.database.mappers import profile_to_row
from csip.infrastructure.database.models.sources import SourceRecord
from csip.infrastructure.database.repositories import (
    PostgresRunRepository,
    PostgresSourceRegistry,
)
from csip.infrastructure.database.session import build_engine

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

EXPECTED_TABLES = {"sources", "runs", "job_events", "artifacts", "raw_observations"}


def _load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env[key] = value
    return env


@pytest.fixture(scope="module")
def env() -> dict[str, str]:
    values = _load_env()
    url = values.get("CSIP_DATABASE_URL")
    if not url:
        pytest.skip("CSIP_DATABASE_URL not configured; skipping live-DB tests")
    engine = build_engine(url)
    try:
        conn = engine.connect()
        conn.execute(text("SELECT 1"))
        conn.close()
    except Exception as exc:
        pytest.skip(f"live database unreachable ({type(exc).__name__}); skipping")
    yield values
    engine.dispose()


@pytest.fixture(scope="module")
def session_factory(env: dict[str, str]):
    engine = build_engine(env["CSIP_DATABASE_URL"])
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture(scope="module")
def run_repository(session_factory) -> PostgresRunRepository:
    return PostgresRunRepository(session_factory)


@pytest.fixture(scope="module")
def source_registry(session_factory) -> PostgresSourceRegistry:
    return PostgresSourceRegistry(session_factory)


@pytest.fixture()
def ingest_session(session_factory):
    """Session used to seed registry rows (writes as csip_ingest)."""
    with session_factory() as session:
        yield session


def _unique_prefix() -> str:
    return f"it{uuid.uuid4().hex[:10]}"


def _approved_profile(source_id: str, domain: str, reference: str) -> SourceProfile:
    return register_source(
        source_id=source_id,
        name="Integration Fixture Supplier",
        canonical_domain=domain,
        owner="integration-tests",
        access_basis=AccessBasis.LOCAL_FIXTURE,
        approved_methods=(AcquisitionMethod.FIXTURE,),
        allowed_scope=AllowedScope(
            allowed_hosts=(domain,),
            allowed_page_families=(PageFamily.PRODUCT_DETAIL,),
        ),
        retention=RetentionPolicy(retain_raw_days=30, retain_artifacts=True),
        approval_evidence=ApprovalEvidence(
            reviewer="integration-review",
            reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
            reference=reference,
        ),
        approval_expires_at=datetime(2027, 11, 1, tzinfo=UTC),
    )


class TestSchemaBaseline:
    def test_all_application_tables_exist(self, env: dict[str, str]) -> None:
        engine = build_engine(env["CSIP_DATABASE_URL"])
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'csip'"
                )
            ).fetchall()
        engine.dispose()
        names = {row[0] for row in rows}
        missing = EXPECTED_TABLES - names
        assert not missing, f"missing tables: {missing}"

    def test_append_only_triggers_are_defined(self, env: dict[str, str]) -> None:
        engine = build_engine(env["CSIP_DATABASE_URL"])
        with engine.connect() as conn:
            triggers = conn.execute(
                text(
                    "SELECT DISTINCT trigger_name FROM information_schema.triggers "
                    "WHERE trigger_schema = 'csip'"
                )
            ).fetchall()
        engine.dispose()
        names = {row[0] for row in triggers}
        assert "trg_job_events_append_only" in names
        assert "trg_raw_observations_append_only" in names


class TestSourceRegistry:
    def test_roundtrip_source_profile(
        self, ingest_session, source_registry: PostgresSourceRegistry
    ) -> None:
        prefix = _unique_prefix()
        source_id = f"{prefix}:fixture-supplier"
        profile = _approved_profile(
            source_id, "it-fixtures.internal", f"ref-{prefix}"
        )

        ingest_session.add(SourceRecord(**profile_to_row(profile)))
        ingest_session.commit()

        loaded = source_registry.get_source(source_id)
        assert loaded is not None
        assert loaded.source_id == source_id
        assert loaded.canonical_domain == "it-fixtures.internal"
        assert loaded.enabled is True
        assert loaded.approval_status == profile.approval_status
        assert loaded.is_currently_approved(datetime.now(UTC))
        assert loaded.permits_method(AcquisitionMethod.FIXTURE)
        assert loaded.rate_limits == profile.rate_limits
        assert loaded.retention == profile.retention
        assert loaded.allowed_scope == profile.allowed_scope
        assert loaded.approval_evidence is not None
        assert loaded.approval_evidence.reference == f"ref-{prefix}"

    def test_unknown_source_returns_none(
        self, source_registry: PostgresSourceRegistry
    ) -> None:
        assert source_registry.get_source(f"no-such-{uuid.uuid4().hex}") is None


class TestRunRepository:
    def test_run_lifecycle(self, run_repository: PostgresRunRepository) -> None:
        prefix = _unique_prefix()
        caller = f"caller-{prefix}"
        key = f"key-{prefix}"
        run_id = f"run-{prefix}"
        job_id = f"job-{prefix}"

        assert run_repository.find_run_id_by_idempotency_key(caller, key) is None

        run_repository.create_run(
            run_id=run_id,
            job_id=job_id,
            request_id=f"req-{prefix}",
            source_id="it:unregistered-source",
            caller_id=caller,
            idempotency_key=key,
            page_family="product_detail",
            initial_state=JobState.QUEUED,
        )

        assert run_repository.find_run_id_by_idempotency_key(caller, key) == run_id
        assert run_repository.get_job_id(run_id) == job_id

        run_repository.append_event(
            event_between(run_id, "submit_collection", None, JobState.QUEUED, "it")
        )
        run_repository.append_event(
            event_between(
                run_id,
                "submit_collection",
                JobState.QUEUED,
                JobState.POLICY_CHECK,
                "it",
            )
        )

        events = run_repository.get_run_events(run_id)
        assert [e.new_state for e in events] == [
            JobState.QUEUED,
            JobState.POLICY_CHECK,
        ]
        assert events[0].previous_state is None
        assert run_repository.get_current_state(run_id) == JobState.POLICY_CHECK

    def test_idempotency_index_is_unique(
        self, run_repository: PostgresRunRepository
    ) -> None:
        prefix = _unique_prefix()
        base = dict(
            request_id=f"req-{prefix}",
            source_id="it:unregistered-source",
            caller_id=f"caller-{prefix}",
            idempotency_key=f"key-{prefix}",
            page_family="product_detail",
        )
        run_repository.create_run(
            run_id=f"run-a-{prefix}",
            job_id=f"job-a-{prefix}",
            initial_state=JobState.QUEUED,
            **base,
        )
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            run_repository.create_run(
                run_id=f"run-b-{prefix}",
                job_id=f"job-b-{prefix}",
                initial_state=JobState.QUEUED,
                **base,
            )


class TestSubmitCollectionJobEndToEnd:
    """The governed path over real Postgres: approval, denial, replay."""

    def _persist_profile(self, ingest_session, profile: SourceProfile) -> None:
        ingest_session.add(SourceRecord(**profile_to_row(profile)))
        ingest_session.commit()

    def test_approved_submission_and_replay(
        self, ingest_session, source_registry, run_repository
    ) -> None:
        from csip.application.dto.collection import SubmissionAccepted

        prefix = _unique_prefix()
        source_id = f"{prefix}:approved-source"
        self._persist_profile(
            ingest_session,
            _approved_profile(source_id, "e2e.internal", f"ref-{prefix}"),
        )
        use_case = build_default_submit_collection_job(source_registry, run_repository)

        command = SubmitCollectionCommand(
            request_id=f"req-{prefix}",
            caller_id="operator:internal",
            source_id=source_id,
            purpose="integration-e2e",
            page_family="product_detail",
            idempotency_key=f"key-{prefix}",
        )
        first = use_case.execute(command)
        assert isinstance(first, SubmissionAccepted)
        assert not first.replayed
        assert first.state == JobState.APPROVED.value

        events = run_repository.get_run_events(first.run_id)
        assert [e.new_state for e in events] == [
            JobState.QUEUED,
            JobState.POLICY_CHECK,
            JobState.APPROVED,
        ]
        assert all(e.actor.startswith("system:") for e in events)

        replay = use_case.execute(command)
        assert isinstance(replay, SubmissionAccepted)
        assert replay.replayed
        assert replay.run_id == first.run_id
        # No duplicate events on replay (FR-02)
        assert len(run_repository.get_run_events(first.run_id)) == 3

    def test_unregistered_source_denied(
        self, ingest_session, source_registry, run_repository
    ) -> None:
        from csip.application.dto.collection import SubmissionRejected

        prefix = _unique_prefix()
        use_case = build_default_submit_collection_job(source_registry, run_repository)
        command = SubmitCollectionCommand(
            request_id=f"req-{prefix}",
            caller_id="operator:internal",
            source_id=f"{prefix}:never-registered",
            purpose="integration-e2e",
            page_family="product_detail",
            idempotency_key=f"key-{prefix}",
        )
        result = use_case.execute(command)
        assert isinstance(result, SubmissionRejected)
        assert result.reason == "source_not_registered"

        states = [
            e.new_state for e in run_repository.get_run_events(result.run_id)
        ]
        assert states == [
            JobState.QUEUED,
            JobState.POLICY_CHECK,
            JobState.BLOCKED_BY_POLICY,
        ]

        replay = use_case.execute(command)
        assert isinstance(replay, SubmissionRejected)
        assert replay.reason == "source_not_registered"
        assert replay.warnings == ("replayed: original denial retained",)
