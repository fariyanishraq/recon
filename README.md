# China Sourcing Intelligence Pipeline (CSIP)

Policy-first, evidence-first ingestion platform that turns **authorized** China-focused
sourcing information into traceable, normalized supplier / product / SKU intelligence.

Governing documents (see `D:\projects\aess\demo\`):

- `goals.md` — outcomes, phases, acceptance gates
- `architecture_blueprint.md` — canonical architecture and invariants
- `project_structure.md` — module boundaries
- `agent.md` — agent operating rules
- `skills.md` — reusable procedures

## Status

Phase 0 (foundation) in progress. See `docs/IMPLEMENTATION_PROGRESS.md`.
No live source collection is implemented or enabled. The system runs in safe
local mode on fixtures only.

## Quickstart

```powershell
# Virtual environment already provisioned at .venv (Python 3.13)
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

# Run the test suite (no network, no live sources)
pytest

# Start the app in safe local mode
python -m csip.main
# -> http://127.0.0.1:8000/healthz
```

## Safety posture

- No acquisition starts without a reviewed, approved, unexpired `SourceProfile`.
- Access-control blocks (403 / CAPTCHA / rate denial) stop the source run; they are
  never retried as transient errors and never worked around.
- Raw observations are append-only and preserved with evidence locators.
- LLM output is advisory; deterministic code validates, resolves, and persists.
