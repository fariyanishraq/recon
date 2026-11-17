# ADR-001: Technology stack and pinned versions

| Field | Value |
|---|---|
| ID | ADR-001 |
| Title | Pin the CSIP stack to verified 2026-11-17 releases |
| Status | accepted |
| Date | 2026-11-17 |

## Context

`architecture_blueprint.md` mandates Chromium/CDP + Browser-use + Crawl4AI +
Agno Workflows/AgentOS + Ollama + self-hosted Supabase/PostgreSQL + one
FastAPI/AgentOS runtime. The Master Development Prompt requires verifying
installed versions against current official documentation before relying on
specific APIs.

## Verification performed (2026-11-17)

Versions checked against PyPI; Agno API surface checked against
docs.agno.com (`agent-os/introduction`, `agent-os/background-execution/durable-queue`):

| Component | Version | Notes |
|---|---|---|
| Python | 3.13.14 | existing venv |
| agno | 3.2.0 | extras `os,postgres,ollama,psycopg`; `agno.os.AgentOS`, `get_app()`, `serve()` |
| Agno durable queue | QueueConfig(durable=True) | Postgres-backed `agno_jobs`, lease+heartbeat, default `max_attempts=1` (fail visibly) — matches blueprint 8.2 |
| crawl4ai | 0.9.5 | JsonCssExtractionStrategy etc.; ships stealth deps but blueprint forbids enabling evasion modes |
| browser-use | 1.0.6 | Pydantic-AI based; CDP access modes |
| fastapi | 0.163.1 | custom routes mount into one lifecycle |
| pydantic | 2.14.3 | settings + DTOs |
| sqlalchemy | 2.1.9 | repositories/migrations |
| alembic | 1.20.1 | migration discipline |
| psycopg | 3.3.9 (+binary) | PostgreSQL driver |

## Decision

Pin exact versions in `pyproject.toml`; commit a transitive lock file
(`requirements.lock` from `pip freeze`). Keep Ollama, Crawl4AI, Browser-use,
and Supabase behind application ports/adapters.

## Consequences

- API usage in later phases must match agno 3.2.0 (`agno.os`, not legacy
  `agno.playground`).
- The whole-job retry budget stays at 1 (enforced in Settings) until
  external side effects are proven idempotent.
- crawl4ai's bundled stealth-related deps are present but must never be
  enabled (blueprint 5.3, goals G2).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Upstream API drift between releases | Medium | Versions pinned; contract tests on adapters before upgrades |
| Playwright browser binaries missing | High (fresh machine) | `playwright install chromium` documented in runbook; defer to Phase 1+ |
