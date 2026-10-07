# v1.8 Execution Plan: Security and Operability Foundations

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.8` (service trust baseline + observability contract + reliability controls)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Implicit trust and uneven telemetry assumptions in local multi-service operation
- Related Workstream: infrastructure-services, a2a-network, evaluation-harness

## Objective
Build the minimum operational foundation required before local hosted-alpha promotion:
1. Enforce trust/auth checks on inter-service calls.
2. Standardize telemetry for traceability from UI action to artifacts.
3. Define and validate reliability controls (timeouts, retries, circuit behavior).

## v1.8 Success Criteria
1. Inter-service trust checks are enforced on benchmark-critical endpoints.
2. Structured logs/events include shared correlation fields (`run_id`, `request_id`, `library_code`).
3. Reliability controls are applied and covered with deterministic tests.
4. CI includes operability gates for trust + telemetry + resilience checks.
5. `uv run pytest -q` remains green.

## In Scope
1. Service-to-service auth/trust policy and enforcement in local stack.
2. Structured logging/event schema and correlation behavior.
3. Timeout/retry/circuit guardrails with clear defaults.
4. Operability-focused tests and CI updates.

## Out of Scope
1. Enterprise IAM/OAuth rollout.
2. Full cloud observability platform deployment.
3. High-scale load testing beyond local alpha profile (`v1.8.5`).

## Dependencies
1. `v1.7` live federation path is operational.
2. `v1.7.5` governance and compatibility gates are active.
3. Existing A2A retry/dedup behavior remains stable.

## Public Interface and Contract Changes
1. Service trust contract
- Files:
  - `services/*/src/*/config.py`
  - `services/*/src/*/routes.py`
- Contract:
  - required auth headers/tokens for inter-service calls
  - standardized unauthorized/forbidden response model

2. Observability contract
- New file:
  - `shared/src/shared/eval/observability_schemas.py`
- Required fields:
  - `timestamp_utc`
  - `service`
  - `operation`
  - `run_id`
  - `request_id`
  - `library_code`
  - `status`

3. Reliability controls contract
- New file:
  - `docs/development/RELIABILITY_POLICY.md`
- Scope:
  - timeout defaults
  - retry budget limits
  - circuit-break thresholds

## Planned Implementation Footprint
1. Service trust/auth
- Update:
  - `services/ill/src/ill/a2a_client.py`
  - `services/registry/src/registry/routes.py`
  - `services/catalog/src/catalog/routes.py`
  - `services/circulation/src/circulation/routes.py`

2. Observability
- New:
  - `shared/src/shared/eval/observability_schemas.py`
- Update:
  - `agents/src/agents/api.py`
  - `scripts/benchmark_run.py`
  - selected service route handlers for correlation propagation

3. Reliability controls and tests
- Update:
  - `services/ill/src/ill/resilience.py`
  - `services/registry/src/registry/a2a_relay.py`
- New:
  - `tests/scenarios/test_service_trust_contract.py`
  - `tests/scenarios/test_observability_contract.py`
  - `tests/scenarios/test_reliability_policy_enforcement.py`

4. Documentation and CI
- Update:
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/development/QUICK_START.md`
  - `.github/workflows/ci.yml`
  - `docs/status/PROJECT_STATUS.md`

## Execution Sequence

### Phase A: Service Trust Baseline (`v1.8-a`)
1. Define local trust model for service-to-service requests.
2. Enforce auth checks on benchmark-critical endpoints.
3. Add denial-path tests for missing/invalid credentials.

Milestone (`v1.8-a`)
1. Owner placeholder: TBD
2. Deliverable: enforced trust layer for inter-service calls.
3. Acceptance checks:
   - unauthorized service requests are rejected
   - valid service credentials pass with no regressions
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_service_trust_contract.py -q`

### Phase B: Observability Contract (`v1.8-b`)
1. Define and implement standardized log/event schema.
2. Propagate correlation IDs through UI -> API -> services -> artifacts path.
3. Add schema checks and correlation assertions.

Milestone (`v1.8-b`)
1. Owner placeholder: TBD
2. Deliverable: correlated telemetry across major components.
3. Acceptance checks:
   - required observability fields present in emitted events
   - run/request IDs are traceable end-to-end
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_observability_contract.py -q`

### Phase C: Reliability Controls (`v1.8-c`)
1. Finalize timeout/retry/circuit policy defaults.
2. Add deterministic fault-path tests for policy behavior.
3. Add CI gates for reliability policy checks.

Milestone (`v1.8-c`)
1. Owner placeholder: TBD
2. Deliverable: reliability controls with deterministic test coverage.
3. Acceptance checks:
   - policy triggers under controlled failure conditions
   - no silent-failure paths in benchmark-critical flows
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_reliability_policy_enforcement.py -q`
   - `uv run pytest -q`

## Parallelization Plan
1. Parallel lane A (auth/trust)
- request signing/token checks
- denial-path tests
- config hardening

2. Parallel lane B (observability)
- schema and correlation fields
- instrumentation updates
- traceability tests

3. Parallel lane C (reliability)
- policy defaults
- deterministic fault tests
- CI gating

4. Merge point
- integrated run proves trust + telemetry + resilience path in one scenario run

## Test Plan and Acceptance Matrix
1. Contract tests
- service trust enforcement
- observability schema/correlation
- reliability-policy behavior

2. Integration tests
- live federation scenario with trust + telemetry assertions
- run artifact includes correlated identifiers

3. Full gates
- `uv run pytest -q`
- `uv run pytest tests/scenarios -q`

## Risks and Mitigations
1. Risk: auth checks break local developer flow.
- Mitigation: explicit local bootstrap credentials and fail-fast diagnostics.

2. Risk: telemetry adds noise or performance overhead.
- Mitigation: bounded structured fields and sampling for verbose events.

3. Risk: reliability policy over-tunes for tests, not real usage.
- Mitigation: keep policy values configurable with documented defaults.

## Definition of Done
`v1.8` is complete when:
1. Service trust is enforced for benchmark-critical inter-service paths.
2. Observability contract is standardized and validated.
3. Reliability controls are documented and deterministic under test.
4. Global regression remains green.

## Follow-On Handoff
After `v1.8` completion, create:
1. `docs/status/V1_8_5_EXECUTION_PLAN.md`

`v1.8.5` should focus on release-candidate hardening (performance budgets, recoverability drills, and promotion gate automation) before `v2.0`.
