# v1.1 Execution Plan: Forensic Judge Foundations

## Doc Header
- Doc Status: Planned
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.1` (trace contract + SQL forensic assertions)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: None
- Related Workstream: evaluation-harness, infrastructure-services, adk-agents, a2a-network

## Objective
Upgrade the benchmark from manifest-only/proxy scoring to deterministic forensic scoring by adding:
1. a canonical trace contract emitted on every benchmark run
2. SQL-based integrity assertions integrated into benchmark artifacts

## v1.1 Success Criteria
1. Benchmark run emits structured trace artifacts with schema validation.
2. Benchmark run executes forensic SQL assertions and reports pass/fail by assertion.
3. JSON and Markdown reports include both trace summary and forensic assertion summary.
4. `uv run pytest -q` remains green after integration.

## In Scope
1. Trace schema and trace writer implementation.
2. Scenario benchmark state persistence for SQL assertion checks.
3. Forensic assertion module with at least:
   - inventory conservation
   - financial integrity
4. Benchmark artifact schema bump and runbook updates.
5. CI integration for trace/assertion checks.

## Out of Scope
1. Null-content trap expansion (`v1.2`).
2. Honey pot/PII red-team pack (`v1.2`).
3. Chaos/fault injector runtime (`v1.3`).
4. Hosted UI feature work (`v2.x`).

## Public Interface and Contract Changes
1. Benchmark artifact schema version bump
- File: `artifacts/benchmark-report.json`
- Change:
  - add `schema_version` (target `1.1`)
  - add `trace_summary`
  - add `forensic_assertions`

2. New trace artifact contract
- File: `artifacts/benchmark-trace.jsonl`
- Format: one JSON event per line, ordered by timestamp.
- Required fields:
  - `trace_id`
  - `run_id`
  - `scenario_id`
  - `event_type`
  - `source`
  - `timestamp`
  - `payload`

3. New forensic assertion artifact
- File: `artifacts/forensic-assertions.json`
- Required fields:
  - `assertion_id`
  - `status` (`pass`/`fail`)
  - `severity`
  - `sql`
  - `result`
  - `evidence`

## Planned Implementation Footprint
1. Shared trace models
- New:
  - `shared/src/shared/eval/__init__.py`
  - `shared/src/shared/eval/trace_schemas.py`
  - `shared/src/shared/eval/trace_writer.py`
- Update:
  - `shared/src/shared/__init__.py`

2. Benchmark runner integration
- Update:
  - `scripts/benchmark_run.py`
  - `scripts/run_benchmark_v1.sh`
- New:
  - `scripts/forensic_assertions.py`
  - `scripts/forensic_sql.py`

3. Scenario state capture for SQL checks
- Update:
  - `tests/scenarios/conftest.py`
  - `tests/scenarios/test_benchmark_scoring.py`
- New:
  - `tests/scenarios/test_trace_schema.py`
  - `tests/scenarios/test_forensic_assertions.py`

4. ADK and A2A trace emission hooks
- Update:
  - `agents/src/agents/benchmark_runner.py`
  - `services/ill/src/ill/routes.py`
  - `services/registry/src/registry/a2a_relay.py`

5. Documentation updates
- Update:
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/status/PROJECT_STATUS.md`
  - `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md`

## Execution Sequence

### Phase A: Trace Contract (`v1.1-a`)
1. Define canonical trace schema and writer.
2. Instrument benchmark runner and ADK deterministic adapter to emit trace events.
3. Emit trace artifact alongside existing benchmark report.
4. Add schema-validation tests and CI check.

Milestone (`v1.1-a`)
1. Owner placeholder: TBD
2. Deliverable: canonical trace artifact generation and validation in benchmark run path.
3. Acceptance checks:
   - `benchmark-trace.jsonl` generated for `--suite scenarios`
   - all events conform to trace schema
   - report includes `trace_summary`
4. Evidence command(s):
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`
   - `uv run pytest tests/scenarios/test_trace_schema.py -q`

### Phase B: SQL Forensic Assertions (`v1.1-b`)
1. Add forensic SQL assertion module and assertion registry.
2. Persist deterministic scenario state databases for post-run SQL evaluation.
3. Implement two required assertions:
   - inventory conservation
   - financial integrity
4. Merge assertion results into benchmark JSON/Markdown artifacts.
5. Add assertion-focused tests and CI gate.

Milestone (`v1.1-b`)
1. Owner placeholder: TBD
2. Deliverable: forensic assertion results embedded in benchmark artifacts.
3. Acceptance checks:
   - assertion file emitted with pass/fail and SQL evidence
   - report contains assertion summary and failing assertion details
   - regression suite remains green
4. Evidence command(s):
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`
   - `uv run pytest tests/scenarios/test_forensic_assertions.py -q`
   - `uv run pytest -q`

## Parallelization Plan
1. Parallel lane A (schema/tooling):
- trace schema package
- trace writer implementation
- artifact contract docs

2. Parallel lane B (assertions/data):
- SQL assertion registry
- deterministic state persistence from scenario fixtures
- assertion tests

3. Merge point:
- integrate both lanes into `scripts/benchmark_run.py`
- update CI and runbook

## Test Plan and Acceptance Matrix
1. Unit
- Trace schema model validation tests.
- SQL assertion query tests against deterministic fixture DBs.

2. Integration
- Benchmark run writes:
  - `benchmark-report.json`
  - `benchmark-report.md`
  - `benchmark-trace.jsonl`
  - `forensic-assertions.json`
- Report integrity checks for schema version and required sections.

3. End-to-end benchmark gate
- `uv sync --all-packages`
- `uv run pytest -q`
- `uv run pytest tests/scenarios -q`
- `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

## Explicit SQL Assertion Definitions for v1.1
1. Inventory Conservation
- Assertion ID: `inventory_conservation_v1`
- Logic: total instances before run equals total instances after run plus transit allocations, grouped by scenario scope.
- Failure condition: net drift not explained by allowed transitions.

2. Financial Integrity
- Assertion ID: `financial_integrity_v1`
- Logic: patron balance delta equals sum of applied charges/payments/waivers in transaction records.
- Failure condition: mismatch between computed ledger delta and recorded account state.

## Risks and Mitigations
1. Risk: scenario fixtures currently use in-memory DBs, limiting post-run SQL evidence.
- Mitigation: add deterministic file-backed DB mode for benchmark runs only.

2. Risk: trace volume can become noisy and expensive.
- Mitigation: keep trace contract focused on deterministic scoring-relevant events in v1.1.

3. Risk: assertion false positives from test setup artifacts.
- Mitigation: isolate assertion scope to benchmark run IDs and seeded fixture boundaries.

4. Risk: artifact schema churn breaks downstream consumers.
- Mitigation: introduce `schema_version` and compatibility tests in CI.

## Definition of Done
`v1.1` is complete when:
1. Trace contract is implemented, validated, and emitted on benchmark runs.
2. Inventory and financial forensic assertions run automatically and report deterministic outcomes.
3. Benchmark artifact schema `1.1` is documented and stable.
4. Global regression command remains green.

## Follow-On Handoff
After `v1.1` completion, create:
1. `docs/status/V1_2_EXECUTION_PLAN.md`
2. `docs/status/V1_3_EXECUTION_PLAN.md`

Those plans should reuse the same artifact schema/versioning discipline introduced in `v1.1`.
