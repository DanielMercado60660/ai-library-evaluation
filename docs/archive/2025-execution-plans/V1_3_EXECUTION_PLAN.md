# v1.3 Execution Plan: Chaos and Resilience

## Doc Header
- Doc Status: Planned
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.3` (deterministic fault injection + resilience scoring)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: None
- Related Workstream: evaluation-harness, infrastructure-services, a2a-network, adk-agents

## Objective
Add deterministic chaos testing and resilience scoring so benchmark runs can prove whether agents recover correctly under degraded infrastructure without sacrificing state consistency, and productionize A2A behavior semantics beyond MVP.

## v1.3 Success Criteria
1. Deterministic chaos scenarios (Tier 1-3) run reproducibly with fixed fault schedules.
2. Benchmark artifacts include explicit resilience metrics and chaos outcome summaries.
3. A2A paths are validated for timeout/retry, denial, malformed payload handling, and idempotent recovery behavior.
4. `uv run pytest -q` remains green after integration.
5. Warning volume is materially reduced so regressions are easier to detect in CI and local runs.

## In Scope
1. Fault injection controller and profile schema for test/benchmark runs.
2. Deterministic chaos scenario pack and resilience-focused assertions.
3. Benchmark scorer/report extensions for resilience metrics.
4. CI and runbook updates for reproducible chaos execution.
5. A2A protocol/runtime contract reconciliation (`docs` + tests + implementation semantics).
6. Warning/deprecation burn-down for noisy hotspots (`datetime.utcnow`, cartesian query warnings, duplicate model declaration warnings).

## Out of Scope
1. Production-grade distributed chaos platform.
2. Hosted UI controls for chaos configuration (`v2.0+`).
3. Cross-model chaos orchestration (`v2.1`).
4. Enterprise SLO management and alerting systems.

## Dependencies
1. `v1.1` trace contract and forensic assertions are available.
2. `v1.2` safety pack schema discipline remains intact (no regression).
3. Deterministic Tier 1-3 baseline scenarios remain runnable without external API dependencies.

## Public Interface and Contract Changes
1. Benchmark report schema bump
- File: `artifacts/benchmark-report.json`
- Change:
  - bump `schema_version` to `1.3`
  - add `chaos_summary`
  - add `resilience_summary`
  - add per-scenario fields:
    - `fault_profile`
    - `recovery_success`
    - `retry_attempts`
    - `degraded_mode_used`
    - `resilience_score`

2. New chaos report artifact
- File: `artifacts/chaos-report.json`
- Required fields:
  - `report_version`
  - `run_id`
  - `fault_profiles[]`
  - `scenario_results[]`
  - `resilience_failures[]`
  - `state_integrity_checks[]`

3. Optional human-readable chaos report
- File: `artifacts/chaos-report.md`
- Content:
  - injected-fault matrix
  - per-scenario recovery outcomes
  - resilience failures and evidence pointers

4. Scenario manifest extension
- File: `tests/scenarios/scenario_manifest.json`
- New optional fields per scenario:
  - `fault_profile` (`timeout` | `http_500` | `malformed_json` | `intermittent_outage`)
  - `fault_schedule` (deterministic injection points)
  - `max_retry_budget` (int)
  - `expected_degradation_mode` (string)

## Planned Implementation Footprint
1. Chaos/resilience modules
- New:
  - `scripts/chaos_controller.py`
  - `scripts/resilience_evaluator.py`
  - `scripts/chaos_profiles.py`
- Update:
  - `scripts/benchmark_run.py`
  - `scripts/benchmark_taxonomy.py`
  - `scripts/run_benchmark_v1.sh`

2. Service hooks for deterministic fault injection
- Update:
  - `services/ill/src/ill/a2a_client.py`
  - `services/ill/src/ill/routes.py`
  - `services/registry/src/registry/a2a_relay.py`

3. Scenario and scorer tests
- New:
  - `tests/scenarios/test_chaos_fault_injection.py`
  - `tests/scenarios/test_resilience_scoring.py`
  - `tests/scenarios/test_chaos_report_schema.py`
  - `tests/scenarios/test_tier3_ill_a2a_chaos.py`
- Update:
  - `tests/scenarios/scenario_manifest.json`
  - `tests/scenarios/test_benchmark_scoring.py`

4. Documentation updates
- Update:
  - `docs/architecture/A2A_PROTOCOL.md`
  - `docs/architecture/SERVICES.md`
  - `docs/architecture/SECURITY.md`
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/status/PROJECT_STATUS.md`
  - `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md`
  - `docs/status/ARCHITECTURE_DRIFT_REPORT.md`

5. Warning burn-down updates
- Update:
  - `services/catalog/src/catalog/` (query joins and warning sources)
  - `services/circulation/src/circulation/` (utcnow usage and model test warnings)
  - test fixtures creating duplicate SQLModel declarations where avoidable

## Execution Sequence

### Phase A: Fault Injection Substrate (`v1.3-a`)
1. Define deterministic fault profile schema and seed controls.
2. Implement chaos controller for timeout/500/malformed/intermittent fault modes.
3. Add service hooks in ILL and registry A2A paths.
4. Add unit tests validating deterministic replay and bounded retry budgets.

Milestone (`v1.3-a`)
1. Owner placeholder: TBD
2. Deliverable: deterministic fault injection layer integrated with benchmark execution path.
3. Acceptance checks:
   - same seed produces identical fault sequence and outcomes
   - retry behavior respects `max_retry_budget`
   - duplicate/late A2A messages remain idempotent under fault load
4. Evidence command(s):
   - `uv run pytest services/ill/tests/integration/test_a2a_retry_timeout.py -q`
   - `uv run pytest services/registry/tests/unit/test_a2a_relay_idempotency.py -q`
   - `uv run pytest tests/scenarios/test_chaos_fault_injection.py -q`

### Phase B: Resilience Scoring and Scenario Pack (`v1.3-b`)
1. Add chaos-enabled Tier 1-3 scenario definitions in manifest and scenario tests.
2. Implement resilience evaluator producing per-scenario resilience metrics.
3. Extend taxonomy mapping for resilience-specific failure classifications.
4. Emit chaos report artifacts and benchmark report schema `1.3` outputs.

Milestone (`v1.3-b`)
1. Owner placeholder: TBD
2. Deliverable: deterministic chaos scenario suite with scored resilience outcomes.
3. Acceptance checks:
   - benchmark report includes required `chaos_summary` and `resilience_summary`
   - chaos report artifacts emitted and schema-valid
   - resilience failures include trace and state evidence pointers
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_resilience_scoring.py -q`
   - `uv run pytest tests/scenarios/test_chaos_report_schema.py -q`
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

### Phase C: Reproducibility and Documentation Closeout (`v1.3-c`)
1. Add one-command chaos benchmark mode in run wrapper.
2. Expand CI to run chaos smoke suite and publish chaos artifacts.
3. Update runbook with fault profile usage, interpretation, and troubleshooting.
4. Update status/DoD docs to mark `v1.3` closure evidence.

Milestone (`v1.3-c`)
1. Owner placeholder: TBD
2. Deliverable: reproducible chaos benchmark path with CI artifact publication.
3. Acceptance checks:
   - documented command path reproduces same outputs from clean env
   - CI uploads `chaos-report.json` and `benchmark-report.json`
   - global regression suite remains green
4. Evidence command(s):
   - `uv sync --all-packages`
   - `uv run pytest -q`
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk --chaos-profile smoke`

### Phase D: A2A Productionization + Warning Burn-Down (`v1.3-d`)
1. Align A2A protocol docs to explicitly separate MVP relay semantics vs deferred full protocol features.
2. Harden ack/idempotency/retry semantics as canonical runtime behavior for v1-v2.
3. Reduce warning noise from top offenders while preserving test coverage.

Milestone (`v1.3-d`)
1. Owner placeholder: TBD
2. Deliverable: productionized A2A semantics and quieter regression output.
3. Acceptance checks:
   - docs and tests describe the same A2A behavior contract
   - warning count is reduced from the 2026-02-09 baseline
   - no regression to scenario determinism or A2A integration coverage
4. Evidence command(s):
   - `uv run pytest services/ill/tests/integration/test_a2a_denial_path.py -q`
   - `uv run pytest services/ill/tests/integration/test_a2a_retry_timeout.py -q`
   - `uv run pytest -q`

## Parallelization Plan
1. Parallel lane A (infrastructure)
- chaos controller core
- ILL/registry hook points
- retry/idempotency hardening

2. Parallel lane B (evaluation)
- resilience evaluator
- taxonomy extensions
- report schema/tests

3. Parallel lane C (scenarios/docs)
- chaos scenario pack
- runbook updates
- CI workflow updates
4. Parallel lane D (noise reduction)
- warning root-cause cleanup
- test-fixture hygiene

5. Merge point
- integrate all lanes in `scripts/benchmark_run.py`
- validate schema `1.3` artifacts end-to-end

## Test Plan and Acceptance Matrix
1. Unit
- fault profile parser validation
- deterministic scheduler replay tests
- resilience scoring calculation tests

2. Integration
- A2A timeout/retry behavior under injected faults
- malformed relay payload handling
- duplicate/late message handling with idempotent acknowledgment

3. Scenario-level
- `uv run pytest tests/scenarios/test_chaos_fault_injection.py -q`
- `uv run pytest tests/scenarios/test_resilience_scoring.py -q`
- `uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q`

4. Full gates
- `uv run pytest -q`
- `uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q`
- `uv run python scripts/benchmark_run.py --suite scenarios --include-adk --chaos-profile smoke`

## Explicit Resilience Assertions for v1.3
1. Retry Budget Compliance
- Assertion ID: `retry_budget_compliance_v1_3`
- Pass condition: retries never exceed scenario-configured budget.
- Fail condition: unbounded or over-budget retries.

2. No Silent Failure
- Assertion ID: `no_silent_failure_v1_3`
- Pass condition: agent reports degraded/unavailable state when operations fail.
- Fail condition: agent reports success without completed state transition.

3. State Integrity Under Fault
- Assertion ID: `state_integrity_under_fault_v1_3`
- Pass condition: inventory and financial invariants remain valid after chaos runs.
- Fail condition: drift detected between expected and persisted state.

4. Graceful Degradation Communication
- Assertion ID: `graceful_degradation_notice_v1_3`
- Pass condition: patron-facing response communicates delay/failure and next action.
- Fail condition: missing or misleading patron communication under fault.

## Risks and Mitigations
1. Risk: chaos hooks make tests flaky.
- Mitigation: deterministic fault schedules and seeded execution only.

2. Risk: resilience score overfits to implementation details.
- Mitigation: derive metrics from manifest-defined expectations and versioned schema.

3. Risk: runtime overhead increases CI duration.
- Mitigation: PR smoke chaos profile; full chaos suite on main/nightly.

4. Risk: fault handling changes obscure true root cause.
- Mitigation: require trace-evidence links for every resilience failure classification.

## Definition of Done
`v1.3` is complete when:
1. Deterministic chaos scenarios run and produce reproducible outcomes.
2. Benchmark and chaos artifacts include required resilience metrics and evidence.
3. A2A recovery paths under denial/timeout/malformed/intermittent conditions are covered by tests.
4. Schema `1.3` and runbook documentation are updated and CI-validated.
5. Global regression command remains green.
6. A2A protocol/runtime drift and warning-noise backlog are materially reduced and logged in `docs/status/ARCHITECTURE_DRIFT_REPORT.md`.

## Follow-On Handoff
After `v1.3` completion, create:
1. `docs/status/V1_4_EXECUTION_PLAN.md`

`v1.4` should focus on deterministic federated data topology (hub/spoke seeding + registry/ILL alignment) while preserving resilience contracts introduced in `v1.3`.
