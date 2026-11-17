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

## Safety rules while developing

- Never point an adapter at a website that is not in `docs/source-profiles/`.
- Never commit `.env`, cookies, tokens, or service-role keys.
- Access-control blocks (403/CAPTCHA/rate denial) are stop conditions, not errors
  to retry — see `runbooks/source-blocked.md` (Phase 4).
