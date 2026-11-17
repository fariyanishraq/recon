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

- **crawl4ai cannot import on the host** — Windows Application Control policy
  blocks its compiled dependencies (`xxhash`, `numpy`). Options: add a policy
  exclusion for `.venv` (recommended) or run extraction in a Linux container.
  Documented in `docs/runbooks/local-development.md`.
- Supabase stack is running with **default placeholder secrets** (demo JWT keys,
  default POSTGRES_PASSWORD/DASHBOARD_PASSWORD) — must be rotated with
  `utils/generate-keys.sh` + `utils/add-new-auth-keys.sh` before any network
  exposure. Local-only until then.

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

## Next actions

1. Resolve the crawl4ai import blocker (policy exclusion or containerized
   extraction) — decision needed from the user.
2. Phase 1: Alembic baseline migration (source registry, runs, job events,
   raw observations) executed as `csip_migrate` against the `csip` schema.
3. Phase 1: Agno Workflow + AgentOS wiring (`QueueConfig(durable=True,
   max_attempts=1)`) with the fixture adapter; `/jobs` submit/status endpoints.

