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

- None for Phase 0. PostgreSQL/Supabase instance (Docker) not yet provisioned —
  required for Phase 1 migrations and durable queue. Docker 29.8.2 is available.

## Next actions

1. Finish Phase 0 exit check: run full suite + lint + app boot in safe local mode.
2. Phase 1: provision self-hosted PostgreSQL (Docker), Alembic baseline migration
   for source registry / runs / job events / raw observations.
3. Phase 1: Agno Workflow (agno 3.2.0) wiring of the approved-plan run through the
   fixture adapter with durable queue (`QueueConfig(durable=True, max_attempts=1)`),
   plus `/jobs` submit/status endpoints with idempotency keys.
4. Phase 1: Crawl4AI extraction profile for one fixture page family (product_detail).
