# v2.0 Execution Plan: Local Hosted Alpha

## Doc Header
- Doc Status: Implemented
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v2.0` (local operator UI for configure, run, replay, and export)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Ad-hoc local UI testing notes
- Related Workstream: infrastructure-services, adk-agents, evaluation-harness, a2a-network

## Objective
Ship a local-first hosted alpha that lets you run the full benchmark workflow end-to-end from UI without public hosting: configure scenario set, launch run, inspect report/trace, and export artifacts. This includes explicit closure of model-abstraction and memory-contract drift needed for reliable local operation.

## v2.0 Success Criteria
1. Local stack can be started with a reproducible command path and accessed at `http://localhost:4200`.
2. Operator can launch benchmark runs from UI and view run state/progress without manual file inspection.
3. UI can render latest report metrics and trace timeline for a selected run.
4. JSON and Markdown artifacts are downloadable from UI for each run.
5. Frontend smoke + live-backend E2E tests are stable in local and CI environments.
6. `uv run pytest -q` remains green after integration.
7. Model adapter boundary and local memory behavior are explicit and tested in the local alpha contract.

## In Scope
1. Local benchmark orchestration API in agents service.
2. Frontend operator workflow pages/components for run/monitor/replay/export.
3. Artifact indexing and run metadata store for local session history.
4. Local-first run and E2E command path documentation.
5. CI smoke job for frontend + local backend integration checks.
6. Model abstraction adapter boundary for future cross-model runs.
7. Local memory behavior contract (session persistence scope, reset semantics, safety boundaries).

## Out of Scope
1. Public hosting, DNS, TLS, cloud deployment, or production infra hardening.
2. Multi-tenant auth, billing, or entitlement systems.
3. Cross-model comparison orchestration (`v2.1`).
4. Enterprise report packaging and compliance workflow automation.

## Dependencies
1. `v1.1` trace and forensic artifact contracts are stable.
2. `v1.2` safety pack, `v1.3` chaos/resilience artifacts, `v1.4` federated seed topology, `v1.5` run-control-plane contracts, `v1.6` operator-hardening baselines, `v1.7` live federation, `v1.7.5` architecture contract gates, `v1.8` security/operability foundations, and `v1.8.5` release hardening gates are available.
3. Existing local service topology remains:
   - agents `8000`
   - catalog `8001`
   - circulation `8002`
   - ill `8003`
   - registry `8004`
   - frontend `4200`

## Public Interface and Contract Changes
1. New benchmark orchestration API (agents service)
- File: `agents/src/agents/api.py`
- Endpoints:
  - `POST /benchmark/runs`
  - `GET /benchmark/runs`
  - `GET /benchmark/runs/{run_id}`
  - `GET /benchmark/runs/{run_id}/report`
  - `GET /benchmark/runs/{run_id}/trace`
  - `GET /benchmark/runs/{run_id}/artifacts`
  - `GET /benchmark/report` (latest-run compatibility alias for existing frontend service)

2. New run metadata contract
- File: `artifacts/runs/index.json`
- Required fields:
  - `run_id`
  - `suite`
  - `status` (`queued|running|passed|failed`)
  - `started_at`
  - `completed_at`
  - `report_path`
  - `trace_path`
  - `artifact_paths[]`

3. Local alpha runner command contract
- New file: `scripts/run_local_alpha.sh`
- Responsibilities:
  - validate dependencies
  - start or verify backend services
  - start frontend
  - print health and URL hints

4. Frontend route/view contract
- Target routes:
  - `/chat`
  - `/runs`
  - `/runs/:runId`
  - `/reports/:runId`
  - `/replay/:runId`

## Planned Implementation Footprint
1. Backend orchestration and run-index modules
- New:
  - `agents/src/agents/benchmark_api_models.py`
  - `agents/src/agents/benchmark_orchestrator.py`
  - `agents/src/agents/run_index.py`
- Update:
  - `agents/src/agents/api.py`

2. Benchmark runner integration
- Update:
  - `scripts/benchmark_run.py` (run-id targeted output path support)
  - `scripts/run_benchmark_v1.sh` (compatibility kept for CLI path)
- New:
  - `scripts/run_local_alpha.sh`

3. Frontend operator UI
- Update:
  - `frontend/src/app/app.component.ts`
  - `frontend/src/app/app.config.ts`
  - `frontend/src/app/core/services/benchmark.service.ts`
- New:
  - `frontend/src/app/features/runs/runs.component.ts`
  - `frontend/src/app/features/run-detail/run-detail.component.ts`
  - `frontend/src/app/features/reports/report-view.component.ts`
  - `frontend/src/app/features/replay/replay.component.ts`
  - `frontend/src/app/shared/models/run.models.ts`

4. Frontend E2E and integration tests
- Update:
  - `frontend/e2e/chat-smoke.spec.ts`
  - `frontend/playwright.config.ts`
- New:
  - `frontend/e2e/run-orchestration.spec.ts`
  - `frontend/e2e/report-replay.spec.ts`
  - `frontend/e2e/live-end-to-end.spec.ts`

5. Documentation updates
- Update:
  - `docs/architecture/MODEL_ABSTRACTION.md`
  - `docs/architecture/MEMORY_SYSTEM.md`
  - `docs/status/ARCHITECTURE_DRIFT_REPORT.md`
  - `frontend/README.md`
  - `docs/development/QUICK_START.md`
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/status/PROJECT_STATUS.md`

## Execution Sequence

### Phase A: Run Orchestration API Finalization (`v2.0-a`)
1. Finalize and harden benchmark run orchestration endpoints introduced in `v1.5`.
2. Validate run-index persistence behavior under UI-triggered workloads.
3. Ensure asynchronous run execution and polling semantics are stable for operator usage.
4. Add alpha-level backend tests for lifecycle and artifact-path integrity.

Milestone (`v2.0-a`)
1. Owner placeholder: TBD
2. Deliverable: callable local benchmark orchestration API with run history.
3. Acceptance checks:
   - `POST /benchmark/runs` creates new run and returns `run_id`
   - run status transitions are persisted deterministically
   - report and trace endpoints return existing artifact payloads
4. Evidence command(s):
   - `uv run pytest agents/tests -q`
   - `uv run python scripts/benchmark_run.py --suite smoke --include-adk`
   - `curl -s http://127.0.0.1:8000/benchmark/runs | jq`

### Phase B: Operator UX Completion (`v2.0-b`)
1. Extend the route-based shell delivered in `v1.6` with full run-launch controls and operator workflows.
2. Complete run list, run detail, report view, and trace replay user journeys.
3. Keep chat and diagnostics as first-class views.
4. Harden route guards and loading/error states for missing runs and failed runs.

Milestone (`v2.0-b`)
1. Owner placeholder: TBD
2. Deliverable: navigable local operator UI that can launch and inspect benchmark runs.
3. Acceptance checks:
   - user can launch run from UI and see status update
   - user can open report and replay views for selected run
   - chat flow remains functional with diagnostics panel
4. Evidence command(s):
   - `cd frontend && npm run build`
   - `cd frontend && npm run e2e`
   - `cd frontend && npm run e2e:live`

### Phase C: End-to-End Local Alpha Hardening (`v2.0-c`)
1. Add local launch wrapper for consistent dev/test startup.
2. Add frontend-live + backend smoke checks in CI.
3. Ensure artifact download flow works for JSON and Markdown reports.
4. Add troubleshooting and known-failure guidance in docs.

Milestone (`v2.0-c`)
1. Owner placeholder: TBD
2. Deliverable: reproducible local alpha runbook and validated E2E smoke path.
3. Acceptance checks:
   - local one-command launch path documented and working
   - CI publishes frontend smoke artifacts/screenshots on failure
   - run/report/replay path works without manual artifact file browsing
4. Evidence command(s):
   - `scripts/run_local_alpha.sh`
   - `uv run pytest -q`
   - `cd frontend && npm run e2e`

### Phase D: Contract Integration Sign-Off (`v2.0-d`)
1. Integrate model-adapter and memory-contract behaviors into UI-driven run flows.
2. Verify local alpha behavior matches the compatibility, reliability, and release-gate contracts introduced pre-`v2.0`.
3. Add final sign-off tests proving contract compliance in operator-driven end-to-end usage.

Milestone (`v2.0-d`)
1. Owner placeholder: TBD
2. Deliverable: operator-validated local alpha contract compliance.
3. Acceptance checks:
   - adapter path and memory-reset behavior are validated through UI-driven flows
   - release gate from `v1.8.5` passes with no blocking failures
   - docs remain aligned with practical local-alpha memory scope (no implied unimplemented dedicated memory service)
4. Evidence command(s):
   - `uv run pytest agents/tests -q`
   - `uv run pytest tests/scenarios -q`
   - `uv run python scripts/release_gate_v2_0_rc.py --strict`

## Parallelization Plan
1. Parallel lane A (backend API)
- orchestration endpoints
- run-index persistence
- artifact endpoint plumbing

2. Parallel lane B (frontend UX)
- multi-route operator shell
- run/report/replay components
- benchmark service updates

3. Parallel lane C (quality/docs)
- Playwright E2E additions
- CI workflow updates
- quick start and runbook updates
4. Parallel lane D (architecture contracts)
- contract adoption in operator workflows
- memory behavior verification in local alpha paths
- architecture drift closure verification

5. Merge point
- validate end-to-end from UI-triggered run to report/replay rendering
- verify CLI path remains backward compatible

## Test Plan and Acceptance Matrix
1. Backend tests
- run lifecycle creation/status retrieval
- invalid run ID handling
- artifact endpoint path validation

2. Frontend tests
- shell launch and route navigation
- run trigger and status polling
- report metrics rendering
- trace replay rendering
- chat message roundtrip

3. E2E tests
- `cd frontend && npm run e2e` (mocked backend smoke)
- `cd frontend && npm run e2e:live` (live local backend smoke)

4. Full gates
- `uv run pytest -q`
- `uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q`
- `cd frontend && npm run build`
- `cd frontend && npm run e2e`

## Explicit Local Alpha Assertions for v2.0
1. Local Launch Viability
- Assertion ID: `local_launch_viability_v2_0`
- Pass condition: stack reachable on localhost with healthy service diagnostics.
- Fail condition: required local components fail to start or health checks fail.

2. UI-to-Runner Continuity
- Assertion ID: `ui_runner_continuity_v2_0`
- Pass condition: UI-created run produces persisted run metadata and report artifacts.
- Fail condition: UI run trigger returns success but no corresponding artifacts exist.

3. Report Fidelity
- Assertion ID: `report_fidelity_v2_0`
- Pass condition: UI report values match artifact JSON values for same run.
- Fail condition: rendered metrics diverge from stored report contract.

4. Replay Trace Integrity
- Assertion ID: `replay_trace_integrity_v2_0`
- Pass condition: replay timeline renders from stored trace for selected run.
- Fail condition: trace retrieval/rendering errors or missing timeline events.

## Risks and Mitigations
1. Risk: frontend/backend contracts drift during rapid iteration.
- Mitigation: shared typed API models and contract tests in CI.

2. Risk: local environment variance (ports/process conflicts) causes false failures.
- Mitigation: central `run_local_alpha.sh` preflight checks and clear diagnostics.

3. Risk: long benchmark runs block API responsiveness.
- Mitigation: asynchronous run execution with status polling and bounded worker queue.

4. Risk: replay UI becomes noisy for large traces.
- Mitigation: add event filtering and scenario-focused default views.

## Definition of Done
`v2.0` is complete when:
1. Local operator can run configure -> launch -> monitor -> replay -> export entirely via UI.
2. New benchmark API endpoints are documented, tested, and stable for local use.
3. Frontend mock and live E2E smoke suites pass consistently.
4. Runbook and quick start provide a reproducible local-alpha path with troubleshooting.
5. Global regression command remains green.
6. Model abstraction and memory-contract drift items are explicitly closed for local alpha scope.

## Follow-On Handoff
After `v2.0` completion, create:
1. `docs/status/V2_1_EXECUTION_PLAN.md`

`v2.1` should focus on cross-model comparison orchestration and normalized leaderboard outputs while reusing the local run/report/replay surface delivered in `v2.0`.
