# CSIP System Overview (Phase 0 baseline)

Canonical authority: `architecture_blueprint.md` (in the project document set).

## Planes (implemented so far)

| Plane | Components | Phase 0 state |
|---|---|---|
| Control plane | FastAPI app (`csip.api.app.create_app`), `/healthz` liveness | Minimal, safe-local; AgentOS lifecycle ownership lands Phase 1 |
| Orchestration plane | Agno Workflow + durable queue | Not yet integrated (Phase 1) |
| Acquisition plane | Acquisition port + fixture adapter | Port + fixture adapter implemented; network adapters deferred to approved-source phases |
| Processing/data plane | Domain contracts (raw observation, candidate, validation report, review) | Contracts implemented; persistence lands Phase 1–3 |
| Operations plane | Structured JSON logging with run IDs, redaction filter | Implemented |

## The one path into acquisition

```
CollectionRequest
   └─> SubmitCollectionJob (application use case, the ONLY entry)
          └─> evaluate_source_policy (deterministic, fail-closed)
                 ├─ denied  -> JobState.BLOCKED_BY_POLICY / APPROVAL_REQUIRED + event
                 └─ approved -> AcquisitionPlan (the sole authorization token)
                                  └─> acquisition adapter (fixture/API/export/browser)
```

There is no API route, workflow step, or adapter method that can obtain an
`AcquisitionPlan` other than through `evaluate_source_policy`, and no
adapter accepts anything but a plan.

## Data layers (contracts ready, persistence in Phase 1+)

Source registry -> raw observation (append-only) -> normalized candidate ->
validation report -> entity resolution -> curated entity / review task,
with evidence locators and redacted, append-only job events throughout.
