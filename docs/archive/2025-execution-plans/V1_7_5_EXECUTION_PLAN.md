# v1.7.5 Execution Plan: Architecture Contract Gates

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.7.5` (ADR governance + API/schema compatibility policy + dependency-boundary enforcement)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Ad-hoc architecture decisions and implicit compatibility assumptions
- Related Workstream: infrastructure-services, adk-agents, evaluation-harness

## Objective
Convert architecture quality from implicit conventions to enforceable gates:
1. Require decision records for architecture-impacting changes.
2. Make API/report schema compatibility testable and versioned.
3. Enforce module boundaries so layering stays coherent as the codebase scales.

## v1.7.5 Success Criteria
1. ADR index and template exist, and architecture-impacting changes are linkable in CI.
2. Compatibility tests protect run/report API payloads and benchmark artifact schema evolution.
3. Static checks catch forbidden imports across `agents`, `services`, `shared`, and scripts.
4. Release checks fail fast when governance or contract rules are violated.
5. `uv run pytest -q` remains green.

## In Scope
1. ADR process scaffolding and CI enforcement.
2. API/schema compatibility policy docs and compatibility tests.
3. Import/dependency boundary map and lint/test checks.
4. Documentation updates for development standards and contribution flow.

## Out of Scope
1. Organization-wide process tooling outside this repository.
2. Public architecture portal or formal RFC platform.
3. Multi-provider runtime rollout (`v2.1+`).

## Dependencies
1. `v1.7` live federation baseline is available.
2. Existing benchmark artifact schema validation tests are stable.
3. CI workflow is active and can host additional gates.

## Public Interface and Contract Changes
1. ADR governance contract
- New files:
  - `docs/architecture/adr/README.md`
  - `docs/architecture/adr/ADR_TEMPLATE.md`
  - `docs/architecture/adr/INDEX.md`
- Behavior:
  - architecture-impacting changes must reference ADR IDs in docs/changelog context.

2. Compatibility policy contract
- New file:
  - `docs/development/CONTRACT_COMPATIBILITY_POLICY.md`
- Scope:
  - benchmark artifact schema versioning rules
  - API additive/breaking change policy
  - deprecation window expectations

3. Boundary enforcement contract
- New file:
  - `docs/development/DEPENDENCY_BOUNDARY_MAP.md`
- Enforcement:
  - explicit allowed/forbidden import paths between layers

## Planned Implementation Footprint
1. Governance and documentation
- New:
  - `docs/architecture/adr/README.md`
  - `docs/architecture/adr/ADR_TEMPLATE.md`
  - `docs/architecture/adr/INDEX.md`
  - `docs/development/CONTRACT_COMPATIBILITY_POLICY.md`
  - `docs/development/DEPENDENCY_BOUNDARY_MAP.md`
- Update:
  - `docs/development/TDD_OOP_GUIDE.md`
  - `docs/status/PROJECT_STATUS.md`

2. CI and checks
- Update:
  - `.github/workflows/ci.yml`
- New:
  - `scripts/check_adr_links.py`
  - `scripts/check_dependency_boundaries.py`

3. Tests
- New:
  - `tests/scenarios/test_contract_compatibility_policy.py`
  - `tests/scenarios/test_dependency_boundaries.py`

## Execution Sequence

### Phase A: ADR Governance Baseline (`v1.7.5-a`)
1. Add ADR template, index, and ownership conventions.
2. Add lightweight checker for ADR ID linkage in architecture-impacting docs.
3. Integrate ADR check into CI.

Milestone (`v1.7.5-a`)
1. Owner placeholder: TBD
2. Deliverable: auditable architecture-decision workflow.
3. Acceptance checks:
   - ADR template and index are discoverable
   - CI fails when required ADR references are missing
4. Evidence command(s):
   - `uv run python scripts/check_adr_links.py --strict`

### Phase B: API/Schema Compatibility Policy (`v1.7.5-b`)
1. Define compatibility rules for benchmark artifacts and run API payloads.
2. Add compatibility tests against golden fixtures.
3. Add changelog policy notes for versioned contract updates.

Milestone (`v1.7.5-b`)
1. Owner placeholder: TBD
2. Deliverable: compatibility policy backed by tests.
3. Acceptance checks:
   - additive changes pass compatibility suite
   - simulated breaking payload changes fail compatibility suite
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_contract_compatibility_policy.py -q`

### Phase C: Dependency-Boundary Enforcement (`v1.7.5-c`)
1. Define layer-boundary map for agents/services/shared/scripts.
2. Implement static checker and CI gate.
3. Add targeted tests proving boundary violations are caught.

Milestone (`v1.7.5-c`)
1. Owner placeholder: TBD
2. Deliverable: enforceable import boundaries.
3. Acceptance checks:
   - forbidden imports fail boundary checks
   - existing code passes under declared rules
4. Evidence command(s):
   - `uv run python scripts/check_dependency_boundaries.py --strict`
   - `uv run pytest tests/scenarios/test_dependency_boundaries.py -q`

## Parallelization Plan
1. Parallel lane A (governance docs)
- ADR structure
- compatibility policy draft
- contributor guidance updates

2. Parallel lane B (enforcement tooling)
- ADR checker
- boundary checker
- CI integration

3. Parallel lane C (tests and fixtures)
- compatibility fixtures
- boundary assertion tests
- regression validation

4. Merge point
- one-command governance + compatibility + boundary checks in CI

## Test Plan and Acceptance Matrix
1. Policy tests
- compatibility rules against fixture payloads
- boundary map conformance checks

2. Tooling checks
- ADR link checker strict mode
- dependency boundary checker strict mode

3. Full gates
- `uv run pytest -q`
- `uv run python scripts/check_adr_links.py --strict`
- `uv run python scripts/check_dependency_boundaries.py --strict`

## Risks and Mitigations
1. Risk: governance overhead slows delivery.
- Mitigation: keep ADR format concise and enforce only architecture-significant changes.

2. Risk: boundary rules become too rigid.
- Mitigation: support explicit, reviewed exemptions with justification.

3. Risk: compatibility policy drifts from implementation.
- Mitigation: encode rules as executable tests and run in CI.

## Definition of Done
`v1.7.5` is complete when:
1. ADR governance is documented and CI-enforced.
2. API/artifact compatibility policy is documented and test-backed.
3. Dependency boundaries are codified and enforced.
4. Global regression remains green.

## Implementation Summary

### Files Created (15)

| Phase | File | Purpose |
|-------|------|---------|
| A | `docs/architecture/adr/README.md` | ADR governance guide |
| A | `docs/architecture/adr/ADR_TEMPLATE.md` | Decision record template |
| A | `docs/architecture/adr/INDEX.md` | Master ADR index |
| A | `docs/architecture/adr/ADR-001-multi-instance-federation.md` | Retroactive: v1.7 decision |
| A | `docs/architecture/adr/ADR-002-registry-hosted-a2a-relay.md` | Retroactive: A2A relay decision |
| A | `docs/architecture/adr/ADR-003-pytest-manifest-benchmark-engine.md` | Retroactive: eval engine decision |
| A | `scripts/check_adr_links.py` | ADR link/section validator |
| B | `docs/development/CONTRACT_COMPATIBILITY_POLICY.md` | Schema compatibility rules |
| B | `tests/fixtures/golden/benchmark-report-v1.1.json` | Golden report fixture |
| B | `tests/fixtures/golden/run-index-v1.5.json` | Golden run index fixture |
| B | `tests/fixtures/golden/scenario-manifest-v1.4.json` | Golden manifest fixture |
| B | `tests/scenarios/test_contract_compatibility.py` | Compatibility tests (6 tests) |
| C | `docs/development/DEPENDENCY_BOUNDARY_MAP.md` | Import boundary rules |
| C | `scripts/check_dependency_boundaries.py` | AST boundary checker |
| C | `tests/scenarios/test_dependency_boundaries.py` | Boundary tests (5 tests) |

### Files Modified (6)

| Phase | File | Change |
|-------|------|--------|
| A/B/C | `.github/workflows/ci.yml` | +3 CI steps (ADR, compatibility, boundaries) |
| D | `docs/status/PROJECT_STATUS.md` | v1.7.5 section |
| D | `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md` | v1.7.5 completion matrix |
| D | `docs/status/V1_7_5_EXECUTION_PLAN.md` | Mark Implemented |
| D | `docs/development/TDD_OOP_GUIDE.md` | Add governance references |
| D | `docs/status/ARCHITECTURE_DRIFT_REPORT.md` | Close v1.7.5 targets |

### Test Baseline
- `uv run pytest -q` -> 558 passed, 6 skipped, 10 xfailed (+11 from v1.7)
- `uv run python scripts/check_adr_links.py --strict` -> 6 passed, 0 failed
- `uv run python scripts/check_dependency_boundaries.py --strict` -> 74 files scanned, 0 violations

## Follow-On Handoff
After `v1.7.5` completion, create:
1. `docs/status/V1_8_EXECUTION_PLAN.md`

`v1.8` should focus on security and operability baselines (service trust, observability contract, and reliability controls) using the contract governance introduced in `v1.7.5`.
