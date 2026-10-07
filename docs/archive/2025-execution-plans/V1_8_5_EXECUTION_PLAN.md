# v1.8.5 Execution Plan: Release Candidate Hardening

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.8.5` (performance budgets + recoverability drills + release-gate automation)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Manual release-readiness judgment before local alpha promotion
- Related Workstream: infrastructure-services, evaluation-harness, adk-agents

## Objective
Create a deterministic release-candidate gate so `v2.0` is a productization step, not an infrastructure gamble:
1. Define and enforce performance budgets for local alpha workflows.
2. Prove recoverability with backup/restore and rollback drills.
3. Automate a single readiness command/report that gates promotion to `v2.0`.

## v1.8.5 Success Criteria
1. Performance budgets are documented and checked in CI.
2. Backup/restore and rollback drills are reproducible and test-backed.
3. A unified release-gate command/report is generated for each candidate run.
4. No blocking issues remain in trust, observability, or reliability gates.
5. `uv run pytest -q` remains green.

## In Scope
1. Performance SLO budget definition and test harness.
2. Recoverability runbook and automated verification drills.
3. Release-candidate checklist automation with artifact output.
4. CI pipeline updates for promotion gate status visibility.

## Out of Scope
1. Cloud-scale performance certification.
2. Multi-region disaster recovery.
3. Commercial launch operations.

## Dependencies
1. `v1.8` trust/observability/reliability foundations are available.
2. `v1.7.5` compatibility and boundary checks are active.
3. `v1.6` route-level operator flows are stable enough for timing measurements.

## Public Interface and Contract Changes
1. Performance budget contract
- New file:
  - `docs/development/PERFORMANCE_BUDGETS.md`
- Scope:
  - route-level latency thresholds
  - benchmark-run completion budget for local alpha profile

2. Recoverability contract
- New file:
  - `docs/development/RECOVERY_AND_ROLLBACK_RUNBOOK.md`
- Scope:
  - backup/restore steps for artifacts/run index/seeded data
  - rollback validation checkpoints

3. Release gate contract
- New file:
  - `scripts/release_gate_v2_0_rc.py`
- Outputs:
  - `artifacts/release-gates/v2_0_rc_report.json`
  - `artifacts/release-gates/v2_0_rc_report.md`

## Planned Implementation Footprint
1. Performance and load smoke harness
- New:
  - `scripts/perf_smoke.py`
  - `tests/scenarios/test_performance_budgets.py`

2. Recoverability automation
- New:
  - `scripts/recovery_drill.py`
  - `tests/scenarios/test_recovery_drill.py`

3. Release-gate automation and CI
- New:
  - `scripts/release_gate_v2_0_rc.py`
  - `tests/scenarios/test_release_gate_report_schema.py`
- Update:
  - `.github/workflows/ci.yml`
  - `docs/status/PROJECT_STATUS.md`

## Execution Sequence

### Phase A: Performance Budgets (`v1.8.5-a`)
1. Define measurable local-alpha budgets for critical workflows.
2. Add deterministic performance smoke script.
3. Fail CI when budgets regress beyond tolerance.

Milestone (`v1.8.5-a`)
1. Owner placeholder: TBD
2. Deliverable: enforceable performance budget gate.
3. Acceptance checks:
   - p95 route latencies are tracked and thresholded
   - benchmark completion budget gate is active
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_performance_budgets.py -q`
   - `uv run python scripts/perf_smoke.py --profile local-alpha`

### Phase B: Recoverability and Rollback (`v1.8.5-b`)
1. Implement backup/restore drill automation.
2. Add rollback validation flow against prior known-good state.
3. Capture drill outputs as artifacts.

Milestone (`v1.8.5-b`)
1. Owner placeholder: TBD
2. Deliverable: repeatable recoverability verification.
3. Acceptance checks:
   - restore drill recreates expected run/report state
   - rollback drill returns stack to runnable smoke baseline
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_recovery_drill.py -q`
   - `uv run python scripts/recovery_drill.py --verify`

### Phase C: RC Gate Automation (`v1.8.5-c`)
1. Aggregate contract/security/reliability/performance/E2E checks into single RC gate.
2. Generate JSON/Markdown readiness report.
3. Integrate gate into CI as promotion prerequisite.

Milestone (`v1.8.5-c`)
1. Owner placeholder: TBD
2. Deliverable: one-command `v2.0` readiness decision.
3. Acceptance checks:
   - gate report includes pass/fail per required check
   - CI marks candidate non-promotable on any blocking failure
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_release_gate_report_schema.py -q`
   - `uv run python scripts/release_gate_v2_0_rc.py --strict`

## Parallelization Plan
1. Parallel lane A (performance)
- budgets and thresholds
- perf smoke harness
- regression reporting

2. Parallel lane B (recoverability)
- backup/restore scripts
- rollback drill
- runbook updates

3. Parallel lane C (promotion automation)
- RC gate aggregator
- report schema and CI artifact publication
- checklist traceability

4. Merge point
- a single RC report artifact demonstrates readiness across all gates

## Test Plan and Acceptance Matrix
1. Performance tests
- route and benchmark budget assertions

2. Recoverability tests
- restore/rollback drill verification

3. Promotion gate tests
- release report schema validation
- failing-gate behavior checks

4. Full gates
- `uv run pytest -q`
- `uv run python scripts/release_gate_v2_0_rc.py --strict`

## Risks and Mitigations
1. Risk: performance checks are noisy across machines.
- Mitigation: use profile-specific tolerances and baseline windows.

2. Risk: rollback drills become stale.
- Mitigation: require periodic drill run in CI/nightly workflow.

3. Risk: gate complexity slows iteration.
- Mitigation: maintain fast PR subset and full strict gate for release candidates.

## Definition of Done
`v1.8.5` is complete when:
1. Performance budgets are codified and CI-enforced.
2. Recovery and rollback drills are automated and reproducible.
3. `v2.0` promotion gate produces deterministic readiness artifacts.
4. Global regression remains green.

## Follow-On Handoff
After `v1.8.5` completion, create:
1. `docs/status/V2_0_EXECUTION_PLAN.md`

`v2.0` should focus on final hosted-alpha UX completion and end-to-end operator workflow sign-off on top of pre-validated architecture and release gates.
