# v1.6 Execution Plan: Operator Surface Hardening

## Doc Header
- Doc Status: Planned
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.6` (route-based operator shell + E2E/CI hardening + local preflight path)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Ad-hoc operator UI and smoke-test notes in chat
- Related Workstream: infrastructure-services, evaluation-harness, adk-agents

## Objective
Harden the operator-facing path on top of the `v1.5` run control plane:
1. Replace single-shell frontend structure with route-based operator surfaces.
2. Validate read-only run/report/replay workflows against run-indexed APIs.
3. Add reliable local preflight/start commands and CI evidence for operator flows.

## v1.6 Success Criteria
1. Frontend supports route-based navigation for `/chat`, `/runs`, `/runs/:runId`, `/reports/:runId`, `/replay/:runId`.
2. Operator views can load run/report/replay data from backend run endpoints.
3. Playwright smoke covers core operator routing and data-loading behavior.
4. CI runs frontend build + operator smoke checks and publishes failure artifacts.
5. Local preflight command path is documented and reproducible.
6. `uv run pytest -q` remains green after integration.

## In Scope
1. Frontend router configuration and route-level feature shells.
2. Benchmark service refactor from static/latest-report model to run-indexed API consumption.
3. Operator E2E coverage (mocked backend plus live-backend smoke).
4. CI workflow extensions for frontend/operator route validation.
5. Local preflight/start wrapper script and runbook updates.
6. Pre-alpha documentation for model/memory contract boundaries feeding `v2.0`.

## Out of Scope
1. Full hosted-alpha completion sign-off (`v2.0`).
2. Cross-model orchestration and leaderboard features (`v2.1`).
3. Public deployment concerns (auth, multi-tenant operations, cloud hosting).

## Dependencies
1. `v1.5` run lifecycle API and run-index contracts are available.
2. Existing benchmark artifacts and schema validation tests remain stable.
3. Local service topology remains consistent with `docker-compose.yml`.

## Public Interface and Contract Changes
1. Frontend route contract
- Files:
  - `frontend/src/main.ts`
  - `frontend/src/app/app.config.ts`
  - `frontend/src/app/app.component.ts`
- Routes:
  - `/chat`
  - `/runs`
  - `/runs/:runId`
  - `/reports/:runId`
  - `/replay/:runId`

2. Frontend benchmark API usage contract
- File: `frontend/src/app/core/services/benchmark.service.ts`
- Change:
  - consume run-indexed backend endpoints
  - remove hard-coded static manifest assumptions from route-level rendering paths

3. Local preflight wrapper
- File: `scripts/run_local_alpha.sh`
- Responsibilities:
  - dependency checks
  - port/process preflight
  - service health probes
  - launch guidance for frontend and backend stack

## Planned Implementation Footprint
1. Frontend routing and views
- New:
  - `frontend/src/app/features/runs/`
  - `frontend/src/app/features/run-detail/`
  - `frontend/src/app/features/reports/`
  - `frontend/src/app/features/replay/`
- Update:
  - `frontend/src/main.ts`
  - `frontend/src/app/app.component.ts`
  - `frontend/src/app/app.config.ts`
  - `frontend/src/app/core/services/benchmark.service.ts`

2. E2E and CI
- New:
  - `frontend/e2e/run-orchestration.spec.ts`
  - `frontend/e2e/report-replay.spec.ts`
- Update:
  - `frontend/playwright.config.ts`
  - `frontend/e2e/chat-smoke.spec.ts`
  - `.github/workflows/ci.yml`

3. Local runner/docs
- New:
  - `scripts/run_local_alpha.sh`
- Update:
  - `frontend/README.md`
  - `docs/development/QUICK_START.md`
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/status/PROJECT_STATUS.md`

## Execution Sequence

### Phase A: Route-Based Operator Shell (`v1.6-a`)
1. Introduce router-based app structure and route components.
2. Move existing chat shell into `/chat` route.
3. Add read-only routes for runs, report detail, and replay timeline.
4. Add error/empty/loading states for missing run IDs and unavailable artifacts.

Milestone (`v1.6-a`)
1. Owner placeholder: TBD
2. Deliverable: route-driven operator shell with stable navigation semantics.
3. Acceptance checks:
   - route navigation works without full page reload
   - invalid run routes show deterministic error state
4. Evidence command(s):
   - `cd frontend && npm run build`
   - `cd frontend && npm run e2e`

### Phase B: Run-Indexed Data Wiring (`v1.6-b`)
1. Refactor benchmark service to consume `v1.5` run endpoints.
2. Replace static scenario assumptions in route-level views with API-driven state.
3. Add report/replay render checks for run-specific artifacts.
4. Validate compatibility fallback for latest report view where needed.

Milestone (`v1.6-b`)
1. Owner placeholder: TBD
2. Deliverable: operator routes backed by run-indexed backend data.
3. Acceptance checks:
   - run list and run detail load from backend API
   - report/replay pages resolve correct `run_id` artifacts
4. Evidence command(s):
   - `cd frontend && npm run e2e`
   - `cd frontend && npm run e2e:live`

### Phase C: CI + Local Preflight Hardening (`v1.6-c`)
1. Add frontend/operator route smoke checks to CI.
2. Add local preflight/start script with explicit diagnostics.
3. Update quick-start/runbook troubleshooting for operator routes.
4. Publish failure artifacts/screenshots in CI for easier triage.

Milestone (`v1.6-c`)
1. Owner placeholder: TBD
2. Deliverable: reproducible local and CI operator-validation path.
3. Acceptance checks:
   - CI runs frontend build + operator smoke tests
   - `run_local_alpha.sh` preflight detects unhealthy/missing services
4. Evidence command(s):
   - `scripts/run_local_alpha.sh`
   - `uv run pytest -q`
   - `cd frontend && npm run e2e`

## Parallelization Plan
1. Parallel lane A (frontend routes)
- router integration
- route component scaffolding
- loading/error state design

2. Parallel lane B (data integration)
- benchmark service refactor
- run-indexed API wiring
- report/replay data mapping

3. Parallel lane C (quality and CI)
- Playwright route suites
- CI workflow integration
- failure artifact publication

4. Parallel lane D (operator docs)
- quick-start/runbook updates
- local preflight script
- troubleshooting guides

5. Merge point
- verify `/runs -> /reports/:runId -> /replay/:runId` continuity against live backend

## Test Plan and Acceptance Matrix
1. Frontend tests
- route navigation smoke
- missing run-id error states
- report/replay render from fixture and live data

2. E2E tests
- `cd frontend && npm run e2e`
- `cd frontend && npm run e2e:live`

3. Backend compatibility checks
- `uv run pytest agents/tests -q`
- `uv run pytest tests/scenarios -q`

4. Full gates
- `uv run pytest -q`
- `cd frontend && npm run build`
- `cd frontend && npm run e2e`

## Explicit Operator Hardening Assertions for v1.6
1. Route Continuity
- Assertion ID: `operator_route_continuity_v1_6`
- Pass condition: chat/runs/report/replay routes render and navigate predictably.
- Fail condition: route dead-ends, navigation loops, or unresolved route errors.

2. Run-to-Report Binding
- Assertion ID: `run_report_binding_v1_6`
- Pass condition: report/replay views load artifacts for the selected `run_id`.
- Fail condition: view renders wrong run data or no data for valid run IDs.

3. CI Operator Coverage
- Assertion ID: `operator_ci_coverage_v1_6`
- Pass condition: CI includes operator-route smoke checks with artifact upload on failure.
- Fail condition: operator regressions can merge without route-level validation evidence.

## Risks and Mitigations
1. Risk: route refactor regresses current chat flow.
- Mitigation: preserve `/chat` as first-class route and retain dedicated smoke test.

2. Risk: frontend/backend contract mismatch causes flaky E2E.
- Mitigation: typed response models and deterministic fixture-backed tests.

3. Risk: CI duration increases significantly.
- Mitigation: keep PR smoke subset lightweight and defer heavier live checks to main/nightly.

4. Risk: local startup complexity blocks operator adoption.
- Mitigation: preflight script with clear diagnostics and step-by-step remediation hints.

## Definition of Done
`v1.6` is complete when:
1. Route-based operator shell is implemented and stable.
2. Run/report/replay routes are backed by run-indexed APIs.
3. Frontend route smoke and E2E checks are integrated into CI.
4. Local preflight/start path is reproducible and documented.
5. Global regression command remains green.

## Follow-On Handoff
After `v1.6` completion:
1. `docs/status/V1_7_EXECUTION_PLAN.md` (created) — live federated services: multi-tenant catalog, real HTTP ILL resolution, end-to-end A2A lifecycle.

`v1.7` upgrades v1.4's fixture-based federation into live service federation before the hosted alpha in `v2.0`.
