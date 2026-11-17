# CSIP Build Report — Session 1

| Field | Value |
|---|---|
| **Date** | 2026-11-17 |
| **Repository** | `D:\projects\aess\backend\recon` (git `master`, commit `afc1bc5`) |
| **Phase completed** | Phase 0 — Repository and architecture foundation |
| **Next phase** | Phase 1 — Fixture-backed vertical slice |
| **Verification** | 85 tests passed · ruff clean · mypy clean (44 files) · live boot HTTP 200 |

---

## 1. What was written so far

### 1.1 Research and dependency baseline

- Verified current versions via PyPI and the official Agno documentation
  (`agent-os/introduction`, `agent-os/background-execution/durable-queue`):

  | Component | Version | Notes |
  |---|---|---|
  | Python | 3.13.14 | existing `.venv` |
  | agno | 3.2.0 | extras `os,postgres,ollama,psycopg` |
  | crawl4ai | 0.9.5 | extraction strategies; stealth deps present but forbidden-to-enable |
  | browser-use | 1.0.6 | Pydantic-AI based, CDP access modes |
  | fastapi | 0.163.1 | single lifecycle |
  | sqlalchemy | 2.1.9 | repositories |
  | alembic | 1.20.1 | migration discipline |
  | psycopg | 3.3.9 | PostgreSQL driver |

- Versions pinned in `pyproject.toml`; full lock committed as
  `requirements.lock` (165 packages); installed into the pre-existing venv.
- Confirmed Agno's `QueueConfig(durable=True, max_attempts=1)` semantics match
  the blueprint §8.2 requirement that a crashed run **fails visibly instead of
  silently re-executing** — this is now enforced in `Settings` (values > 1
  refuse to boot until idempotency is proven).

### 1.2 Source code — 20 modules under `src/csip/`

| Layer | Files | What it does |
|---|---|---|
| `domain/sources` | `entities.py`, `value_objects.py` | `SourceProfile` governance record with enforced invariants: enabled ⇒ approved ⇒ recorded evidence + expiry. Access bases, acquisition-method complexity order, page families, rate limits, scope, retention, stop conditions, host matching. |
| `domain/jobs` | `entities.py` | `CollectionRequest`, explicit `JobState` lifecycle (11 normal + 10 exception states with terminal/exception classification), `JobEvent`. |
| `domain/acquisition` | `entities.py` | `AcquisitionPlan` (the sole authorization token), `AcquisitionArtifact` (fingerprint mandatory), artifact types. |
| `domain/observations` | `entities.py` | `RawObservation` (frozen ⇒ append-only), `NormalizedCandidate` (populated values require model provenance; blank raw values rejected), `ValidationReport` (hard failures cannot pass). |
| `domain/evidence` | `entities.py` | `EvidenceLocator` — locator + supporting snippet required for every populated critical field. |
| `domain/reviews` | `entities.py` | `ReviewTask` — resolution requires reviewer, decision, timestamp, and reason. |
| `services/source_policy.py` | 1 | **The deterministic authorization gate.** Fail-closed on: unregistered / disabled / unapproved / expired / revoked source, missing access basis, method not approved, scope mismatch, unknown caller. Selects lowest-complexity approved method; clamps page volume to source ceilings; emits a `PolicyDecision` whose `AcquisitionPlan` is the only thing adapters accept. |
| `application/use_cases/submit_collection_job.py` | 1 | **The single route into acquisition.** Loads the profile, runs the gate, creates a durable run, records explicit `queued → policy_check → approved` (or `blocked_by_policy` / `approval_required`) transition events, returns safe accept/reject DTOs. |
| `application/ports` | `acquisition.py`, `repositories.py` | Vendor-neutral protocols: acquisition adapter (plan-only), source registry, run repository, event sink. |
| `application/dto` | `collection.py` | `SubmitCollectionCommand`, `SubmissionAccepted`, `SubmissionRejected` (denials keep run correlation). |
| `adapters/acquisition/fixtures/` | 1 | Safe local-mode adapter: reads synthetic fixture files only, SHA-256 fingerprints, **zero network side effects** (proven with a probe HTTP server in a contract test), refuses non-fixture plans. |
| `infrastructure/config/settings.py` | 1 | Fail-fast typed config (pydantic-settings): CDP bind must be loopback/private (`0.0.0.0` wildcard rejected; 0.0.0.0/8 rejected), whole-job retry budget locked to 1, DB URL mandatory outside local mode. |
| `infrastructure/observability/logging.py` | 1 | Structured JSON logging with run/correlation IDs via contextvars; redaction filter on the **handler** (covers child loggers) covering message **and** `extra` payload keys/values. |
| `infrastructure/clock.py` | 1 | Injectable `Clock` (`UtcClock`, `FrozenClock`). |
| `shared/` | 4 | Safe error taxonomy (16 stable codes; 403/CAPTCHA/rate denial is its own **stop** code, never transient), typed IDs with validation, secret redaction, minimal `Result` type. |
| `api/app.py`, `main.py` | 2 | One FastAPI lifecycle, public `/healthz` liveness (separate from privileged telemetry), safe error → HTTP mapping, safe-local boot entrypoint. |

### 1.3 Tests — 85 passing

| Suite | Files | Covers |
|---|---|---|
| `tests/unit/` | 4 | Domain invariants (every entity), full policy-denial matrix (incl. expiry boundary, host matching, clamping), config safety rules, logging/redaction incl. `extra` scrubbing |
| `tests/integration/` | 1 | End-to-end submission through the gate: event traceability, actor attribution, denial routing, idempotent replay (same key ⇒ same run, no duplicate transitions), multi-key isolation |
| `tests/contract/` | 1 | Adapter contract: fingerprint + metadata, method refusal, missing fixture, no-network proof |
| `tests/security/` | 1 | Error taxonomy stability, API error shaping, status mapping |
| Harness | `support.py`, `in_memory.py` | Governed fixture source builders; in-memory registry/run store |

### 1.4 Documentation and operations

- `docs/adr/ADR-000-template.md`, `ADR-001-tech-stack.md` (pinned stack + verified
  APIs + risks), `ADR-002-domain-stdlib-only.md` (dependency-boundary decision).
- `docs/IMPLEMENTATION_PROGRESS.md` — living progress tracker (phase, goal IDs,
  implemented table, blockers, next actions).
- `docs/architecture/system-overview.md` — the "one path into acquisition" flow.
- `docs/runbooks/local-development.md` — install/test/run/lint + safety rules.
- `docs/source-profiles/README.md` — onboarding template; no live source registered.
- `alembic.ini` + `db/env.py` — migration skeleton that **fails closed** without
  `CSIP_DATABASE_URL`; `db/script.py.mako` template.
- `pyproject.toml`, `requirements.lock`, `.env.example`, `.gitignore`, `README.md`.
- Git initialized; root commit `afc1bc5` (78 files, ~3.9k lines).

### 1.5 Verified results

| Check | Command | Result |
|---|---|---|
| Test suite | `pytest` | **85 passed**, 0 skipped |
| Lint | `ruff check src tests` | **All checks passed** |
| Types | `mypy` | **Success — no issues in 44 source files** |
| Boot (safe local mode) | `python -m csip.main` → `GET /healthz` | **HTTP 200** `{"status":"ok","service":"csip"}` |

Every failure encountered during the session was root-caused and fixed
(redaction gap on `extra` values, logging filter inheritance bug, duplicate
replay transitions, policy reason ordering, CDP `0.0.0.0` wildcard-bind
acceptance). No test was weakened to make the suite green.

---

## 2. What still needs to be built

### Phase 1 — Fixture-backed vertical slice (next)

1. **Docker PostgreSQL** — provision the system of record (application schema +
   separate Agno runtime role/namespace). *Docker 29.8.2 is installed; the
   daemon was not reachable during session 1 and must be started.*
2. **Alembic migrations** — source registry, runs, job events, raw
   observations, evidence tables; least-privilege roles.
3. **Real repositories** — SQLAlchemy implementations behind the defined ports.
4. **Agno 3.2.0 workflow + AgentOS** — explicit stages wired to
   `SubmitCollectionJob` and the fixture adapter;
   `AgentOS` + `QueueConfig(durable=True, max_attempts=1)` becomes the single
   API lifecycle owner.
5. **API routes** — `/jobs` submit (with `Idempotency-Key` header) and status.
6. **Crawl4AI extraction profile** — versioned `product_detail` schema, first
   labeled fixtures, evidence locators.

**Exit gate:** integration test proving request → workflow → fixture artifact →
extraction → raw persistence → status, with a traceable run ID and
duplicate-safe replay.

### Phase 2 — Ollama normalization

Inference port + adapter, versioned prompt/schema, labeled multilingual
evaluation set (Chinese, mixed CN/EN, prices/currency/units, MOQ, variants,
tables, missing values, conflicts, adversarial injection), deterministic
output validation, abstention behavior.

### Phase 3 — Entity resolution and curated persistence

Supplier / platform-account / product-family / SKU boundaries; match pipeline
(exact stable IDs → deterministic keys → fuzzy-as-candidate-only); new /
update / duplicate / conflict / review-required decisions; unique constraints,
transactions, audited review workflow.

### Phase 4 — First approved live source

**Blocked on a human decision:** an approved `SourceProfile` with documented
access basis, owner sign-off, scope, rate policy, and expiry. Then the
least-complex approved adapter; Browser-use navigation with dedicated Chromium
profile + localhost CDP only if genuinely needed; stop-on-challenge tests.

### Phase 5 — Operational hardening

Bounded concurrency, backpressure, cancellation at safe checkpoints, circuit
breakers, worker-restart/DB-outage/model-error recovery tests, backup/restore
drill, dashboards, runbooks (source-blocked, parser-drift, failed-jobs,
credential rotation).

### Phase 6 — Controlled expansion

Additional sources/page families through the same governance, benchmark, and
operational acceptance process.

---

## 3. What is needed from the environment / user

| # | Item | Purpose | Status |
|---|---|---|---|
| 1 | **Docker daemon started** (Docker Desktop) | PostgreSQL + later self-hosted Supabase | Docker 29.8.2 installed; daemon not reachable yet |
| 2 | **Decision: plain PostgreSQL first vs. full Supabase stack from the start** | Shapes compose file + migration targets | Needs user decision |
| 3 | **Playwright Chromium download** (`playwright install chromium`, ~150 MB) | Crawl4AI/Browser-use runtime from Phase 1 onward | Can be run in the venv on request |
| 4 | **Ollama installed + model pulled** (e.g. `qwen2.5:7b-instruct`) | Phase 2 local inference | Not yet installed/confirmed |
| 5 | **A real source approval** (owner, access basis, written permission/terms review, expiry) | Phase 4 gate — no live collection without it | Cannot be invented; requires human sign-off |
| 6 | **API auth preference** for Phase 1 (shared service key vs. per-user JWT — AgentOS supports both) | Shapes `/jobs` endpoints | Needs user decision |

---

## 4. Safety and data-integrity posture (current)

- No acquisition is reachable without a current, approved, unexpired
  `SourceProfile`; the gate is deterministic and fail-closed, and adapters
  structurally cannot act without an `AcquisitionPlan`.
- Raw observations are frozen/append-only; candidates require model
  provenance and evidence; hard validation failures cannot pass.
- Whole-job retries are locked to 1 attempt in configuration until external
  side effects are proven idempotent.
- Secrets are redacted at logging and event boundaries; `.env` files are
  gitignored; no credentials exist in the repository.
- No live website was accessed at any point; all work is fixture-backed.

---

*Prepared by the CSIP implementation agent — see `docs/IMPLEMENTATION_PROGRESS.md`
for the living progress tracker.*
