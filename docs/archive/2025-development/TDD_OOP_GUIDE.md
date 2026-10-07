# TDD and OOP Guide

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Engineering standards for tests, architecture boundaries, and implementation quality
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Legacy long-form roadmap material embedded in this guide
- Related Workstream: infrastructure-services

## Principles
- Write tests first for business rules and integration boundaries.
- Keep service boundaries explicit: routes -> domain logic -> persistence.
- Use typed schemas and explicit state transitions.
- Prefer evidence-backed documentation updates after behavior changes.

## Test Strategy
- Unit: deterministic business rules and validation.
- Integration: service boundaries, state transitions, MCP tool behavior.
- Scenario: end-to-end flows and adversarial behavior checks.

## Definition of Done (Engineering)
- Relevant unit/integration tests added or updated.
- `uv run pytest` run and failures triaged.
- Documentation updates include evidence pointers.
- No new conflicting global status declarations outside `docs/status/PROJECT_STATUS.md`.
- Architecture-impacting changes have an ADR (see `docs/architecture/adr/README.md`).
- Schema/API changes follow the compatibility policy (see `docs/development/CONTRACT_COMPATIBILITY_POLICY.md`).
- No forbidden cross-layer imports (see `docs/development/DEPENDENCY_BOUNDARY_MAP.md`).

## Governance References
- **ADR governance**: `docs/architecture/adr/README.md` — when and how to write architecture decision records
- **Compatibility policy**: `docs/development/CONTRACT_COMPATIBILITY_POLICY.md` — schema versioning, additive/breaking change rules
- **Dependency boundaries**: `docs/development/DEPENDENCY_BOUNDARY_MAP.md` — allowed/forbidden import paths between layers

## Evidence Commands
```bash
uv run pytest
uv run python scripts/check_adr_links.py --strict
uv run python scripts/check_dependency_boundaries.py --strict
rg -n "TODO|FIXME" services agents
rg -n "Doc Header" docs
```
