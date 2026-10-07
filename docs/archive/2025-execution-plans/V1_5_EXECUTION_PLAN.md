# v1.5 Execution Plan: Run Control Plane

## Doc Header
- Doc Status: Planned
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.5` (run-scoped artifact model + async benchmark orchestration API)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Ad-hoc benchmark run launch notes tied to "latest report" behavior
- Related Workstream: infrastructure-services, evaluation-harness, adk-agents

## Objective
Establish a stable run control plane so benchmark execution is addressable by `run_id`:
1. Move from single latest-artifact semantics to run-scoped artifact directories.
2. Introduce asynchronous orchestration endpoints in the agents API.
3. Preserve deterministic benchmark artifact contracts and CLI compatibility.

## v1.5 Success Criteria
1. Benchmarks can be launched and queried via run lifecycle endpoints.
2. Artifacts are partitioned under `artifacts/runs/<run_id>/` with indexed metadata.
3. Status transitions are deterministic (`queued -> running -> passed|failed`).
4. Existing CLI path (`scripts/run_benchmark_v1.sh`) remains supported.
5. `uv run pytest -q` remains green after integration.

## In Scope
1. Run metadata models and run-index persistence contract.
2. Async orchestration API endpoints for create/list/get/report/trace/artifact views.
3. Runner integration for run-specific output directories.
4. API and integration tests for lifecycle transitions and path integrity.
5. Documentation updates for control-plane commands and troubleshooting.

## Out of Scope
1. Route-driven operator UX and dashboard-level polish (`v1.6+`).
2. Full hosted-alpha user journey sign-off (`v2.0`).
3. Cross-model orchestration and leaderboard workflows (`v2.1`).

## Dependencies
1. `v1.4` federated seed topology and deterministic scenario contracts are available.
2. Existing benchmark artifacts remain canonical for schema validation.
3. Agents service remains local runtime gateway for benchmark and chat APIs.

## Public Interface and Contract Changes
1. Run orchestration API
- File: `agents/src/agents/api.py`
- Endpoints:
  - `POST /benchmark/runs`
  - `GET /benchmark/runs`
  - `GET /benchmark/runs/{run_id}`
  - `GET /benchmark/runs/{run_id}/report`
  - `GET /benchmark/runs/{run_id}/trace`
  - `GET /benchmark/runs/{run_id}/artifacts`
  - `GET /benchmark/report` (compatibility alias to latest successful run)

2. Run index contract
- File: `artifacts/runs/index.json`
- Required fields:
  - `run_id`
  - `suite`
  - `status`
  - `started_at`
  - `completed_at`
  - `artifact_dir`
  - `report_path`
  - `trace_path`
  - `artifact_paths[]`

3. Runner output contract
- File: `scripts/benchmark_run.py`
- Change:
  - support run-targeted artifact output directories
  - preserve existing default artifact outputs for backward compatibility

## Planned Implementation Footprint
1. Orchestration and run-index modules
- New:
  - `agents/src/agents/benchmark_api_models.py`
  - `agents/src/agents/benchmark_orchestrator.py`
  - `agents/src/agents/run_index.py`
- Update:
  - `agents/src/agents/api.py`

2. Benchmark runner integration
- Update:
  - `scripts/benchmark_run.py`
  - `scripts/run_benchmark_v1.sh`

3. Tests
- New:
  - `agents/tests/integration/test_benchmark_run_lifecycle.py`
  - `agents/tests/integration/test_run_index_integrity.py`
- Update:
  - `agents/tests/integration/test_benchmark_runner.py`

4. Documentation updates
- Update:
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/development/QUICK_START.md`
  - `docs/status/PROJECT_STATUS.md`
  - `docs/status/VERSION_LADDER_PROPOSAL.md`

## Execution Sequence

### Phase A: Run Identity and Artifact Partitioning (`v1.5-a`)
1. Define run metadata schema and index file format.
2. Add per-run artifact directory layout.
3. Add compatibility bridge to legacy latest-report paths.
4. Add deterministic run-id and artifact-path validation tests.

Milestone (`v1.5-a`)
1. Owner placeholder: TBD
2. Deliverable: versioned run index and artifact partitioning contract.
3. Acceptance checks:
   - each run yields unique `run_id` and scoped artifact directory
   - latest-report compatibility endpoint still resolves
4. Evidence command(s):
   - `uv run pytest agents/tests/integration/test_run_index_integrity.py -q`
   - `uv run python scripts/benchmark_run.py --suite smoke`

### Phase B: Async Orchestration API (`v1.5-b`)
1. Implement run create/list/get endpoints.
2. Add asynchronous lifecycle updates and status persistence.
3. Wire run-specific report/trace/artifact retrieval endpoints.
4. Add error handling for missing/invalid run identifiers.

Milestone (`v1.5-b`)
1. Owner placeholder: TBD
2. Deliverable: callable benchmark orchestration API with deterministic status transitions.
3. Acceptance checks:
   - `POST /benchmark/runs` returns `run_id` and initial status
   - `GET /benchmark/runs/{run_id}` reflects lifecycle state changes
   - report/trace endpoints return run-scoped artifacts
4. Evidence command(s):
   - `uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q`
   - `curl -s http://127.0.0.1:8000/benchmark/runs | jq`

### Phase C: Integration and Closeout (`v1.5-c`)
1. Align benchmark wrapper scripts and runbook commands to orchestration contracts.
2. Validate deterministic outputs across smoke/scenarios suites.
3. Update status docs and changelog evidence.
4. Confirm global regression stability.

Milestone (`v1.5-c`)
1. Owner placeholder: TBD
2. Deliverable: production-ready local run control plane for benchmark lifecycle operations.
3. Acceptance checks:
   - runbook and quick-start reflect orchestration API path
   - regression suite remains green after integration
4. Evidence command(s):
   - `uv run pytest -q`
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

## Parallelization Plan
1. Parallel lane A (API and lifecycle)
- endpoint implementation
- status machine and validation
- lifecycle test coverage

2. Parallel lane B (artifact contracts)
- run-index schema and persistence
- run-scoped artifact pathing
- compatibility alias handling

3. Parallel lane C (runner/docs)
- runner output integration
- wrapper script updates
- runbook and quick-start updates

4. Merge point
- validate end-to-end create -> run -> fetch report/trace/artifacts lifecycle

## Test Plan and Acceptance Matrix
1. Unit
- run metadata model validation
- status transition guard tests
- run index read/write consistency tests

2. Integration
- API lifecycle transition tests
- artifact endpoint path validation tests
- invalid run-id behavior tests

3. Full gates
- `uv run pytest agents/tests -q`
- `uv run pytest tests/scenarios -q`
- `uv run pytest -q`

## Explicit Run Control Assertions for v1.5
1. Run Identity Determinism
- Assertion ID: `run_identity_contract_v1_5`
- Pass condition: each benchmark launch has stable, unique `run_id` and indexed metadata.
- Fail condition: duplicate/missing run IDs or missing index entries.

2. Lifecycle State Integrity
- Assertion ID: `run_lifecycle_state_machine_v1_5`
- Pass condition: transitions follow allowed state graph with terminal status recorded.
- Fail condition: invalid transitions or stuck non-terminal states.

3. Artifact Path Fidelity
- Assertion ID: `run_artifact_path_fidelity_v1_5`
- Pass condition: report/trace/artifact endpoints resolve to run-scoped files.
- Fail condition: endpoint returns mismatched or missing artifact paths.

## Risks and Mitigations
1. Risk: run-index churn breaks existing consumers.
- Mitigation: preserve `GET /benchmark/report` compatibility alias and document migration.

2. Risk: async lifecycle introduces race conditions under repeated launches.
- Mitigation: enforce atomic index updates and deterministic status transitions.

3. Risk: artifact sprawl increases storage and cleanup complexity.
- Mitigation: include retention/cleanup guidance in runbook with explicit ownership.

## Definition of Done
`v1.5` is complete when:
1. Orchestration endpoints are implemented and lifecycle-tested.
2. Run-scoped artifact directories and index contract are stable.
3. Legacy benchmark report consumption remains backward-compatible.
4. Documentation includes reproducible orchestration command path.
5. Global regression suite remains green.

## Follow-On Handoff
After `v1.5` completion, create:
1. `docs/status/V1_6_EXECUTION_PLAN.md`

`v1.6` should focus on route-based operator surfaces, CI/E2E hardening, and local preflight reliability on top of the `v1.5` run control plane.
