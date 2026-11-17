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
| **crawl4ai** | **blocked** (needs compiled `xxhash` + `numpy`; no pure fallback) |

Consequence: the Crawl4AI extraction stage cannot run on the host until one of:

1. an App Control exclusion is added for this project's `.venv`
   (recommended — proper fix), or
2. extraction workloads run inside a Linux Docker container (no Windows DLL policy).

If the venv is recreated, re-apply the `.pyd` rename via:

```powershell
Get-ChildItem -Recurse -Filter "*.pyd" ".venv\Lib\site-packages\sqlalchemy" |
  Rename-Item -NewName { $_.Name + ".disabled" }
```

## Safety rules while developing

- Never point an adapter at a website that is not in `docs/source-profiles/`.
- Never commit `.env`, cookies, tokens, or service-role keys.
- Access-control blocks (403/CAPTCHA/rate denial) are stop conditions, not errors
  to retry — see `runbooks/source-blocked.md` (Phase 4).
