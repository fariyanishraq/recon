# CSIP Build Report — Session 2

| Field | Value |
|---|---|
| **Date** | 2026-11-17 |
| **Repository** | `D:\projects\aess\backend\recon` (git `master`, commits `3450b89` → this session) |
| **Phase advanced** | Phase 1 — Database foundation on live Supabase (migration + repositories + integration tests) |
| **Environment** | User-provided self-hosted Supabase (Postgres 17.6.1, Supavisor pooler, Docker) |
| **Verification** | 93 tests passed (85 in-memory + 8 live-DB) · ruff clean · mypy clean (54 files) · all baseline DB checks passed (`scripts/db/verify_baseline.py`) |

---

## 1. Environment discovery and provisioning

### 1.1 Self-hosted Supabase discovered via Docker

- 12 containers running, including `supabase-db` (Postgres **17.6.1**) behind
  `supabase-pooler` (Supavisor).
- Connection path: **Supavisor session mode on host port 5432**; usernames must
  carry the tenant suffix (`<role>.your-tenant-id`) or the pooler rejects the
  connection with `ENOIDENTIFIER`. Transaction mode is on 6543 (not used yet).
- Admin password obtained at runtime from `docker inspect supabase-db` and
  **never printed**; role passwords are random `secrets.token_urlsafe(24)`
  values written only to the gitignored `.env`.

### 1.2 Windows Application Control policy — compiled-extension blockers

This machine blocks loading compiled `.pyd`/DLL files ("An Application
Control policy has blocked this file"). Impact and workarounds:

| Component | Status | Resolution |
|---|---|---|
| psycopg (binary pq wrapper) | blocked | **Project switched to `pg8000`** (pure Python). URLs are `postgresql+pg8000://`; `session.py::require_pg8000_url` refuses any other driver. |
| SQLAlchemy compiled accelerators (8 `.pyd`) | blocked | SQLAlchemy ships pure-Python twins; the 8 `.pyd` files were renamed `.pyd.disabled` inside `.venv`. Import now succeeds. |
| agno.db.postgres / alembic | OK after the above | The Phase 1 critical path (durable queue + migrations) works on the host. |
| **crawl4ai** | **still blocked** | Requires compiled `xxhash` + `numpy`; no pure fallback. **Awaiting user decision**: App Control exclusion for `.venv` (recommended) vs. containerized extraction in Linux Docker. |

Documented in `docs/runbooks/local-development.md` with the re-apply command
for recreated venvs.

### 1.3 Roles and schemas (least privilege)

`scripts/db/setup_supabase_roles.py` (idempotent; `--reset` rotates passwords):

| Object | Purpose |
|---|---|
| Schema `csip` | Application-owned tables (all migrations target it) |
| Schema `agno` | AgentOS runtime tables — owned by `csip_agno`, never touched by app migrations |
| Role `csip_migrate` | DDL only (Alembic); owns all migration-created objects |
| Role `csip_ingest` | DML on app tables (+ sequences); default privileges scoped to objects created by `csip_migrate` |
| Role `csip_read` | SELECT only — verified that INSERT is denied |
| Role `csip_agno` | AgentOS runtime owner |

Gotchas recorded: the pooler needs the tenant-suffixed username; `pg8000.native`
is autocommit (no `.commit()`); `CREATE ROLE` cannot take bind parameters
(password escaped and inlined); default-privilege grants must be scoped
`FOR ROLE csip_migrate` (they apply to the creating role, not the schema) and
must cover **sequences** as well as tables (auto-increment columns).

---

## 2. Baseline migration — executed and verified live

### 2.1 Schema (`db/versions/0001_baseline.py`, revision `0001_baseline`)

Five tables in schema `csip`: `sources` (change-controlled registry),
`runs`, `job_events`, `artifacts`, `raw_observations`.

Idempotency indexes: `uq_runs_caller_idempotency` (caller, key),
`uq_artifacts_run_fingerprint` (run, fingerprint),
`uq_raw_obs_run_artifact_field` (run, artifact, field).

**Append-only enforcement lives in the database, not just app code
(SK-10):** `trg_job_events_append_only` and `trg_raw_observations_append_only`
call `csip._reject_mutation()` and raise on any UPDATE or DELETE.

### 2.2 Verification against the live database (all passed)

`scripts/db/verify_baseline.py` checks:

1. All five tables + `csip_alembic_version` present in schema `csip`;
2. both append-only triggers defined;
3. **every table owned by `csip_migrate`**;
4. `csip_ingest` can INSERT into all five tables;
5. UPDATE and DELETE on `job_events` and `raw_observations` are **rejected**
   by the trigger (`P0001 table ... is append-only`);
6. `csip_read` can SELECT but its INSERT is **denied** (`42501`).

Alembic bookkeeping was moved into the `csip` schema
(`version_table_schema="csip"` in `db/env.py`) since `csip_migrate` has
CREATE only there; migrations run preferentially under `CSIP_DB_MIGRATE_URL`.

---

## 3. Code written this session

| Layer | Files | What it does |
|---|---|---|
| `infrastructure/database/session.py` | 1 | Engine factory; **enforces the pure-Python pg8000 driver** (refuses URLs that would hit blocked DLLs). |
| `infrastructure/database/models/{sources,runs,observations}.py` | 3 | ORM models for the `csip` schema (source registry, runs/job_events, artifacts/raw_observations) with the same unique indexes as the migration. |
| `infrastructure/database/mappers.py` | 1 | `SourceProfile` ↔ row mapping at the infrastructure boundary (ADR-002: stdlib domain dataclasses, pydantic only at boundaries). |
| `infrastructure/database/repositories/postgres_sources.py` | 1 | `PostgresSourceRegistry` — `SourceRegistryPort` over `csip.sources`. |
| `infrastructure/database/repositories/postgres_runs.py` | 1 | `PostgresRunRepository` — `RunRepositoryPort` over `csip.runs`/`csip.job_events`; `append_event` is INSERT-only (events are immutable), current-state pointer updated on the run row. |
| `db/versions/0001_baseline.py` | 1 | Baseline migration with append-only triggers (see §2). |
| `scripts/db/setup_supabase_roles.py` | 1 | Idempotent role/schema bootstrap (§1.3). |
| `scripts/db/verify_baseline.py` | 1 | Live-DB verification suite (§2.2). |
| `tests/integration/test_postgres_baseline.py` | 1 | 8 integration tests against the live DB, skipping cleanly when unreachable. |

---

## 4. Tests — 93 passing (85 in-memory + 8 live-DB)

The integration suite exercises the **real** governed path over Postgres:

- Schema baseline: all five tables present; both append-only triggers defined.
- Source registry roundtrip: persist a full approved `SourceProfile`, reload
  it, and confirm scope/rate-limits/retention/evidence/expiry survive and
  `is_currently_approved` holds.
- Run lifecycle: create → events `queued → policy_check` → current state;
  duplicate `(caller, idempotency_key)` insertion rejected by the unique index
  (IntegrityError).
- End-to-end through `SubmitCollectionJob` on the live DB:
  - approved source → `queued → policy_check → approved`, actor
    `system:policy_gate`, replay returns the same run with **no duplicate
    events** (FR-02);
  - unregistered source → `blocked_by_policy` with safe
    `source_not_registered` reason; denial retained on replay.

Test rows use fresh unique ids each run (append-only audit rows are never
deleted — by design); the suite skips when `CSIP_DATABASE_URL` is absent or
the database is unreachable, keeping the suite green on any machine.

---

## 5. Safety invariants upheld

- **No acquisition without an approved profile** — policy gate runs on every
  submission, over the real registry, fail-closed (proven live).
- **Append-only raw observations/events** — enforced by database triggers,
  verified by attempting UPDATE/DELETE as the write role and receiving
  rejection.
- **Least privilege** — verified that the read role cannot write and every
  table is owned by the migration role.
- **No secrets in code/logs** — passwords only in gitignored `.env`; URLs are
  redacted in logs (`db/env.py::_redact`); nothing credential-bearing was
  printed or committed.

---

## 6. Blockers / decisions needed

1. **crawl4ai on host** — blocked by compiled `xxhash`/`numpy`. Options:
   (a) App Control exclusion for this project's `.venv` (recommended), or
   (b) containerized extraction in Linux Docker. Blocking the Crawl4AI
   extraction stage of Phase 1.
2. **Supabase default secrets** — stack runs with the public demo values
   (`POSTGRES_PASSWORD`, JWT keys, dashboard password). Rotate with
   `utils/generate-keys.sh` + `utils/add-new-auth-keys.sh` before any network
   exposure; rerun `setup_supabase_roles.py --reset` afterwards to refresh
   role passwords.

## 7. Addendum — both open decisions executed (same session)

### 7.1 Decision 1: crawl4ai unblocked via containerized extraction

The App Control exclusion (option a) requires a manual admin policy change on
Windows and cannot be applied programmatically, so the working path was
implemented: **crawl4ai runs in Linux Docker** (`containers/extraction/`):

- `extractor.py` — FastAPI service on **loopback-only** `127.0.0.1:8100`
  (goals G8): `GET /healthz`, `POST /extract_raw` (extract from
  **already-captured** artifact HTML, no network — the pipeline-preferred
  path), `POST /extract` (fetch + extract; caller must pass
  policy-authorized URLs only — the service performs no policy checks
  itself).
- HTTP + LXML strategies only (no Playwright/Chromium in the image);
  browser-dependent strategies wait until policy explicitly approves
  `browser_pages`.
- Deterministic structured JSON output; the LLM never performs extraction
  (blueprint invariant).
- Smoke test: `docker run --rm csip-extraction:latest python extractor.py --selftest`.

### 7.2 Decision 2: Supabase secret rotation — applied and verified

The stack had been running with the public demo placeholder secrets. Applied
the official scripts inside a throwaway `node:22-bookworm` container
(secrets suppressed from all output):

1. `utils/generate-keys.sh --update-env` — JWT_SECRET, ANON_KEY,
   SERVICE_ROLE_KEY, SECRET_KEY_BASE, REALTIME_DB_ENC_KEY, VAULT_ENC_KEY,
   PG_META_CRYPTO_KEY, LOGFLARE tokens, S3 keys, MINIO password,
   **POSTGRES_PASSWORD**, DASHBOARD_PASSWORD.
2. `utils/add-new-auth-keys.sh --update-env` — EC P-256 keypair
   (JWT_KEYS/JWKS), opaque API keys (`sb_publishable_`/`sb_secret_`),
   ES256 asymmetric API keys; uncommented the asymmetric-key env lines in
   docker-compose.yml.

Then, in dependency order:

1. `ALTER ROLE ... PASSWORD '<new>'` for **every non-`csip_*` login role**
   (all Supabase service roles share `POSTGRES_PASSWORD` at init; hex
   password inline-safe; done before service restart so services
   reconnecting with the new env var succeed).
2. Deleted Supavisor tenant rows (`_supavisor.tenants` / `users` in the
   `_supabase` database) — `volumes/pooler/pooler.exs` creates the tenant
   **only once**, baking in the then-current `POSTGRES_PASSWORD`; deleting
   forces re-provisioning with the new one on startup.
3. `docker compose up -d` — all services recreated with the new environment.

Verification (`scripts/db/verify_rotation.py` — prints no secrets):

| Check | Result |
|---|---|
| New admin password connects via pooler | ✅ |
| Supavisor tenant re-provisioned (`your-tenant-id`) | ✅ |
| `csip_migrate/ingest/read/agno` still connect (passwords were independent/random) | ✅ |
| Auth health with **new opaque publishable key** | ✅ HTTP 200 |
| REST with **new SERVICE_ROLE_KEY** | ✅ HTTP 200 |
| REST with anon key on a data route | ✅ (404 table-not-found = passed gateway + PostgREST; OpenAPI introspection is RBAC-blocked by design) |
| Studio login with **new DASHBOARD_PASSWORD** (`/project/default`) | ✅ HTTP 200 |
| All 11 containers healthy | ✅ |

Backups kept in the supabase directory (never committed):
`.env.backup-20261117`, `docker-compose.yml.backup-20261117`, plus the
scripts' own `.old` copies.

### 7.3 Updated next steps

1. Agno Workflow + AgentOS wiring: durable queue (`QueueConfig(durable=True,
   max_attempts=1)`) against the `agno` schema via `CSIP_AGNO_DB_URL`.
2. `/jobs` submit + status endpoints with idempotency keys.
3. Fixture end-to-end slice — now **including** the extraction container:
   approved plan → fixture capture → `/extract_raw` → raw observations
   persisted with fingerprints.

