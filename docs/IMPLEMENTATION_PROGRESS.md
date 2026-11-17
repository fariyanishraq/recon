# CSIP Implementation Progress

Living document. Update per session; never let it replace implementation.

**Last updated:** 2026-11-17 (session 1)

## Current phase

**Phase 0 — Repository and architecture foundation** (in progress, near exit gate)

## Goal IDs advanced this session

- **G1** (governed source onboarding): `SourceProfile` invariants + deterministic
  policy evaluator, fail-closed on every uncertainty.
- **G8** (secure observable operation): structured JSON logging with run/correlation
  IDs, secret redaction filter, safe error taxonomy, CDP bind-host validation,
  whole-job retry budget locked to 1 until idempotency is proven.
- **G7** (one controlled API surface): single FastAPI lifecycle with `/healthz`
  (liveness separated from privileged telemetry).

## Implemented (verified by tests)

| Deliverable | Where | Tests |
|---|---|---|
| Domain contracts: SourceProfile, CollectionRequest, AcquisitionPlan, AcquisitionArtifact, RawObservation, NormalizedCandidate, ValidationReport, EntityResolutionDecision*, ReviewTask, JobEvent | `src/csip/domain/` | `tests/unit/test_domain_contracts.py` |
| Deterministic source-policy evaluator | `src/csip/services/source_policy.py` | `tests/unit/test_source_policy.py` |
| Policy-gated submission use case (only route into acquisition) | `src/csip/application/use_cases/submit_collection_job.py` | `tests/integration/test_submit_collection_job.py` |
| Acquisition port + fixture adapter (no network side effects) | `src/csip/adapters/acquisition/fixtures/` | `tests/contract/test_acquisition_fixture.py` |
| Typed config with fail-fast validation (CDP exposure, retry budget, DB requirement) | `src/csip/infrastructure/config/settings.py` | `tests/unit/test_settings.py` |
| Structured logging, run IDs, redaction | `src/csip/infrastructure/observability/logging.py`, `src/csip/shared/redaction.py` | `tests/unit/test_logging_and_redaction.py` |
| Safe error taxonomy + API error shaping | `src/csip/shared/errors.py`, `src/csip/api/app.py` | `tests/security/test_error_taxonomy_and_api.py` |

\* EntityResolutionDecision: represented by the review-task contracts; the full
resolution engine is Phase 3.

## Stack verification

Verified against PyPI and docs.agno.com on 2026-11-17 — see `docs/adr/ADR-001-tech-stack.md`.
Pinned in `pyproject.toml`; installed into `.venv` (Python 3.13.14).

## Decisions

- ADR-001: pinned stack versions.
- ADR-002: domain layer is stdlib-only (dataclasses); pydantic at trust boundaries.

## Blockers

- ~~crawl4ai cannot import on the host~~ — **resolved 2026-11-17** by
  containerizing the extraction stage (`containers/extraction/`, Linux
  Docker, loopback-only). A Windows App Control exclusion for `.venv` remains
  an optional host-native alternative (manual admin action).
- ~~Supabase stack running with default placeholder secrets~~ — **resolved
  2026-11-17** by full secret rotation (JWT keys, POSTGRES_PASSWORD,
  dashboard password, vault/encryption keys, opaque API keys) with
  Supavisor tenant re-provisioning; verified by
  `scripts/db/verify_rotation.py`.

## Environment provisioned (2026-11-17, session 2)

- Self-hosted Supabase stack (user-provided, Docker) — Postgres 17.6.1 behind
  Supavisor pooler (session mode :5432, transaction :6543, tenant
  `your-tenant-id`, usernames must be `<role>.<tenant_id>` through the pooler).
- Schemas `csip` (application) and `agno` (AgentOS runtime) created.
- Least-privilege roles `csip_migrate`, `csip_ingest`, `csip_read`, `csip_agno`
  created with random passwords (stored only in gitignored `.env` via
  `scripts/db/setup_supabase_roles.py` — idempotent, `--reset` rotates).
- All four role connections verified through the pooler; `Settings` validates.
- `db/env.py` now prefers `CSIP_DB_MIGRATE_URL` (DDL role) for migrations.
- SQLAlchemy imports on host after disabling its blocked compiled accelerators
  (pure-Python twins); `agno.db.postgres` (durable queue) imports OK.

## Baseline migration live (2026-11-17, session 2 continued)

- `0001_baseline` executed as `csip_migrate` against the `csip` schema
  (Alembic bookkeeping kept in `csip.csip_alembic_version`).
- Five tables: `sources`, `runs`, `job_events`, `artifacts`,
  `raw_observations`, with idempotency unique indexes and **database-level
  append-only triggers** on `job_events` / `raw_observations`.
- Verified live via `scripts/db/verify_baseline.py`: table ownership, ingest
  DML, UPDATE/DELETE rejection, read-role write denial — all passed.
- Postgres repositories added (`PostgresSourceRegistry`,
  `PostgresRunRepository`) implementing the application ports, with
  `SourceProfile` row mapping in `infrastructure/database/mappers.py`.
- 8 live-DB integration tests added (`tests/integration/test_postgres_baseline.py`):
  schema baseline, registry roundtrip, run lifecycle + idempotency uniqueness,
  and end-to-end `SubmitCollectionJob` approval/denial/replay over Postgres.
  Suite skips cleanly when the DB is unreachable.
- Test totals: **93 passed** (85 in-memory + 8 live-DB); ruff + mypy clean.
- Session report: `docs/reports/session-2-report.md`.

## Next actions

1. Agno Workflow + AgentOS wiring (`QueueConfig(durable=True,
   max_attempts=1)`) with the fixture adapter; `/jobs` submit/status endpoints.
2. Fixture end-to-end slice: submit → approved plan → fixture capture →
   `/extract_raw` on the extraction container → artifacts + raw observations
   persisted with fingerprints.

