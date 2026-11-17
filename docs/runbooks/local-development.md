# Local Development Runbook

## Prerequisites

- Python 3.13 venv at `.venv` (already provisioned)
- Docker (for PostgreSQL/Supabase from Phase 1 onward)

## Install

```powershell
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Run tests

```powershell
pytest            # full suite, no network access
pytest tests/unit # fast subset
```

## Run the app (safe local mode)

```powershell
python -m csip.main
# http://127.0.0.1:8000/healthz
```

Safe local mode (`CSIP_LOCAL_MODE=true`, the default) permits fixture-backed
work only. Setting `CSIP_LOCAL_MODE=false` without a database URL refuses to boot.

## Lint / format

```powershell
ruff check src tests
ruff format src tests
```

## Browser binaries (Phase 1+)

Crawl4AI/Browser-use need a Chromium driver the first time browser extraction
runs locally:

```powershell
.\.venv\Scripts\playwright.exe install chromium
```

This is not required for the fixture-based test path.

## Windows Application Control policy (IMPORTANT, this machine)

This machine blocks several **compiled** Python extensions
(`An Application Control policy has blocked this file`). Findings as of
2026-11-17:

| Component | Status on host |
|---|---|
| sqlalchemy compiled accelerators (`*.pyd`) | blocked → **workaround applied**: the 8 `.pyd` files were renamed to `.pyd.disabled` inside `.venv`; SQLAlchemy ships pure-Python twins and imports fine (slightly slower) |
| agno / agno.db.postgres / alembic | OK after the above |
| browser-use | OK |
| psycopg binary DLL | blocked → project uses **pg8000** (pure Python) as SQLAlchemy driver (`postgresql+pg8000://` URLs) |
| **crawl4ai** | **blocked on host** (needs compiled `xxhash` + `numpy`; no pure fallback) → **resolution (2026-11-17)**: extraction runs in a Linux Docker container (`containers/extraction/`); see below. A Windows App Control exclusion for `.venv` would also work but requires a manual admin policy change. |

Consequence: the Crawl4AI extraction stage runs as the **`csip-extraction`**
container (Linux Docker), bound to `127.0.0.1:8100` only. See
`containers/extraction/README.md`. Host-side code talks to it over HTTP.

If the venv is recreated, re-apply the `.pyd` rename via:

```powershell
Get-ChildItem -Recurse -Filter "*.pyd" ".venv\Lib\site-packages\sqlalchemy" |
  Rename-Item -NewName { $_.Name + ".disabled" }
```

## Extraction container (crawl4ai on this machine)

```powershell
docker compose -f containers\extraction\docker-compose.yml up -d --build
```

- `GET http://127.0.0.1:8100/healthz` — liveness
- `POST /extract_raw` — extract from already-captured artifact HTML (no
  network; the pipeline-preferred path)
- `POST /extract` — fetch + extract a URL; the caller must only pass
  policy-authorized URLs

## Supabase secret rotation (2026-11-17)

The self-hosted stack previously ran with the public demo placeholder
secrets. Rotation applied via the official scripts
(`utils/generate-keys.sh --update-env`, `utils/add-new-auth-keys.sh
--update-env`) inside a `node:22-bookworm` container, plus:

1. `ALTER ROLE ... PASSWORD` for every non-`csip_*` login role (service roles
   all share `POSTGRES_PASSWORD` in the supabase image).
2. Deletion of the Supavisor tenant rows in `_supabase._supavisor`
   (`tenants`/`users`) so `volumes/pooler/pooler.exs` re-provisions the
   tenant with the new password on startup (the tenant is created only once,
   with the then-current password).
3. `docker compose up -d` recreation of all services.

Pre-change backups: `.env.backup-20261117`,
`docker-compose.yml.backup-20261117`. Post-rotation verification:
`scripts/db/verify_rotation.py` (admin via pooler, tenant re-provisioned,
csip roles unchanged, new keys accepted by the gateway; never prints
secrets). The `csip_*` role passwords in the recon `.env` were random and
unchanged by this.

## Safety rules while developing

- Never point an adapter at a website that is not in `docs/source-profiles/`.
- Never commit `.env`, cookies, tokens, or service-role keys.
- Access-control blocks (403/CAPTCHA/rate denial) are stop conditions, not errors
  to retry — see `runbooks/source-blocked.md` (Phase 4).
