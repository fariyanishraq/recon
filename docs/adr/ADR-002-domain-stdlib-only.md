# ADR-002: Domain layer uses stdlib dataclasses, not pydantic

| Field | Value |
|---|---|
| ID | ADR-002 |
| Title | Keep domain entities free of pydantic |
| Status | accepted |
| Date | 2026-11-17 |

## Context

`project_structure.md` rule 4.1: "`domain/` depends only on the standard
library and stable internal domain primitives." Pydantic is used heavily at
trust boundaries (API DTOs, settings), which tempts domain models to become
pydantic models.

## Options considered

1. Pydantic models everywhere — convenient, but couples the domain to a
   serialization library and blurs the boundary.
2. Stdlib `dataclasses` + enums in `domain/`; pydantic only in `api/`,
   `application/dto`, and `infrastructure/config` — enforces the dependency
   rule mechanically (import graph checkable).

## Decision

Option 2. Domain entities are frozen dataclasses with `__post_init__`
invariant checks. Serialization and request validation happen at trust
boundaries (adapters, API, config).

## Consequences

- Domain invariants are enforced in constructors and remain testable without
  third-party validation semantics.
- Conversion code is needed between API DTOs and domain entities; kept thin.
- Hand-written invariant checks are deliberate: they are the deterministic
  validation the architecture requires (no model self-validation).

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Boilerplate conversion code grows | Medium | Review DTO mapping at API boundaries; keep mappers in `api/` |
| Invariant drift across entities | Low | Contract tests cover every entity's invariants |
