# Workstream: Evaluation Harness

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Scenario testing, red-team coverage, benchmark scoring, and comparison reproducibility
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Fragmented evaluation status notes
- Related Workstream: evaluation-harness

## Objective
Deliver repeatable and policy-aligned evaluation outcomes with deterministic scoring and comparison outputs.

## Current Reality
1. Tiered scenario packs and manifest-driven benchmark scoring are implemented.
2. Safety, chaos, resilience, and federation scenario suites are active.
3. `v2.1` adds run-to-run comparison and leaderboard aggregation for completed runs.
4. `v2.1` now supports scenario-scoped execution (`scenario_ids`) for assistant card click-to-run flows.

## Implemented Footprint
1. Core benchmark/scoring tooling:
   - `scripts/benchmark_run.py`
   - `tests/scenarios/scenario_manifest.json`
   - `tests/scenarios/test_benchmark_scoring.py`
2. Compatibility and contract gates:
   - `tests/scenarios/test_contract_compatibility.py`
   - `tests/fixtures/golden/run-index-v1.5.json`
3. v2.1 comparison coverage:
   - `agents/tests/integration/test_benchmark_run_lifecycle.py`
   - `agents/src/agents/benchmark_comparison.py`
4. Assistant scenario execution and trace observability:
   - `scripts/benchmark_run.py`
   - `frontend/src/app/core/services/assistant-run.service.ts`
   - `frontend/src/app/shared/utils/audit-trace.mapper.ts`
   - `frontend/e2e/assistant-scenario-run.spec.ts`

## Remaining Gaps
1. Full cross-provider comparison matrix (currently Gemini variants only).
2. Stress/performance test coverage for leaderboard aggregation at larger run volumes.
3. Evaluator-ready benchmark scenario tutorials tied to live analytics workflows.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: comparison fixture pack covering tie-break ordering and edge cases.
   - Acceptance checks: leaderboard order remains deterministic under tie conditions.
   - Evidence command(s): `uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q`
2. Owner placeholder: TBD
   - Deliverable: larger synthetic run corpus for aggregation/load checks.
   - Acceptance checks: compare/leaderboard APIs remain within response-time budget.
   - Evidence command(s): `uv run pytest tests/scenarios -k "benchmark or contract" -q`
3. Owner placeholder: TBD
   - Deliverable: scenario-to-analytics walkthrough doc for evaluators.
   - Acceptance checks: walkthrough references live `/analytics` flow and deep-link compare URLs.
   - Evidence command(s): `rg -n "analytics|compare|leaderboard" docs`

## Definition of Done
Evaluation outcomes are deterministic, synthetic-world compliant, and reproducibly comparable across completed benchmark runs.

## Dependencies
- world-data-governance
- adk-agents
- infrastructure-services

## Risks
- Scenario drift reducing longitudinal comparability.
- Non-deterministic fixture updates affecting score reproducibility.
