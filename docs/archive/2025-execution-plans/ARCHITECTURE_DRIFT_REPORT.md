# Architecture Drift Report

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-09 (v2.0 closure verified)
- Scope: Drift map between `docs/architecture/*` design intent and current implementation, with versioned closure plan
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Ad-hoc architecture drift notes in chat
- Related Workstream: infrastructure-services, adk-agents, a2a-network, evaluation-harness, world-data-governance

## Purpose
Make drift explicit so architecture decisions are intentional, versioned, and testable rather than accidental.

## Verified Baseline (2026-02-09)
- Test baseline: `uv run pytest -q` -> `624 passed, 6 skipped, 10 xfailed` (v2.0 local hosted alpha; +8 model/memory contract tests).
- Golden runtime stack is active in code:
  - ADK agents: `agents/src/agents/*.py`
  - MCP tools: `services/*/src/*/mcp_server.py`
  - A2A runtime relay: `services/registry/src/registry/routes.py`, `services/registry/src/registry/a2a_relay.py`, `services/ill/src/ill/a2a_client.py`
- Remaining TODOs in ILL are non-core placeholders:
  - `services/ill/src/ill/routes.py`
  - `services/ill/src/ill/tasks.py`

## Drift Matrix

| Architecture Doc | Intended Design | Current Reality | Drift Classification | Planned Closure Version |
|---|---|---|---|---|
| `docs/architecture/OVERVIEW.md` | End-to-end layered platform with scenario runner, chaos controller, model swapper, metrics collector | Core layers exist; v1.2 added safety evaluation; v1.4 added federated hub/spoke topology with 5 libraries, 635-book partitioned corpus, and ILL federation scenarios | `Closed (v1.4)` | v1.4 ✅ |
| `docs/architecture/SERVICES.md` | Separate registry (`7001`) and A2A broker (`7002`) services | Registry is on `8004` and hosts A2A relay endpoints directly; docs updated in v1.2 | `Closed (v1.2)` | v1.2 ✅ |
| `docs/architecture/AGENTS.md` | Front desk delegates to catalog, circulation, and ILL specialist paths | Front desk delegates to all three via ADK sub-agents + FunctionTool; `ILLEscalationAgent` created and tested | `Closed (v1.2)` | v1.2 ✅ |
| `docs/architecture/A2A_PROTOCOL.md` | JSON-RPC-first framing and full protocol narrative | MVP relay semantics (send/poll/ack) are documented with retry contract, dedup behavior, and deferred full protocol features | `Closed (v1.3)` | v1.3 ✅ |
| `docs/architecture/EVALUATION.md` | Class-based scenario engine abstraction | Implemented path is pytest + manifest + benchmark scorer + chaos/resilience extensions; docs reconciled | `Closed (v1.3)` | v1.3 ✅ |
| `docs/architecture/SECURITY.md` | Strong outbound/inbound validation layers and leakage prevention | A2A outbound payload validation enforced (`_validate_outbound_payload`); PII canary scanner + null-content trap evaluator added; compliance report generation | `Closed (v1.2)` | v1.2 ✅ |
| `docs/architecture/MODEL_ABSTRACTION.md` | Provider-agnostic `BaseLLM` interface and adapters | ADR-005 codifies Gemini-only contract for v2.0; full adapter layer deferred | `Closed (v2.0 contract)` | v2.0 ✅ (contract), v2.1 (cross-model execution) |
| `docs/architecture/MEMORY_SYSTEM.md` | Dedicated multi-tier memory architecture | ADR-006 codifies session-only memory for v2.0; full memory tiers deferred | `Closed (v2.0 contract)` | v2.0 ✅ (contract), v2.1+ (persistent memory) |

## Kept / Enhanced / Deferred / Dropped

### Kept
1. Fictional synthetic world as anti-memorization benchmark substrate.
2. ADK + MCP + A2A as core runtime combination.
3. Hub-and-spoke main library plus partner libraries.

### Enhanced
1. A2A now has tested relay behavior (happy path, denial, timeout/retry, idempotent ack).
2. Evaluation is now deterministic and artifact-driven (manifest + benchmark report + forensic assertions).
3. (v1.2) Safety evaluation layer: null-content trap evaluator, PII canary scanner, compliance report generator.
4. (v1.2) A2A outbound payload validation prevents PII leakage across library boundaries.
5. (v1.2) Front desk ILL delegation as first-class ADK sub-agent with fallback routing.
6. (v1.3) Deterministic chaos testing framework with call-index fault injection and resilience scoring.
7. (v1.3) A2A hardened with exponential backoff + jitter retry and relay-level message dedup.
8. (v1.3) Warning burn-down: zero `datetime.utcnow()` deprecation warnings remaining.
9. (v1.4) Federated hub/spoke topology: 5 libraries, 635-book partitioned corpus with manifest-driven ownership.
10. (v1.4) ILL federation scenarios proving local-miss/network-hit behavior with A2A notification verification.
11. (v1.5) Run control plane: run-scoped artifact directories, async orchestration API, run index persistence with file locking.
12. (v1.7.5) Architecture contract gates: ADR governance with CI enforcement, API/schema compatibility policy with golden fixtures, AST-based dependency boundary enforcement.
13. (v1.8) Service trust baseline: shared-secret auth middleware on all 5 services with auto-injection in HTTP client.
14. (v1.8) Observability contract: correlation ID ContextVar propagation, structured log schema, RequestCorrelationMiddleware.
15. (v1.8) Reliability controls: ADR-004 codifying timeout/retry/CB defaults, AST-based resilience policy checker.
16. (v1.8.5) Performance budgets: in-process ASGI health timing, budget thresholds, perf_smoke.py CI gate.
17. (v1.8.5) Recoverability drills: backup/restore/verify automation with SHA256 checksum verification.
18. (v1.8.5) Release gate automation: unified 7-gate aggregator with promotable/blocked status and JSON+Markdown reports.
19. (v2.0) Architecture contract closure: ADR-005 (Gemini-only model) and ADR-006 (session-only memory) with 8 contract enforcement tests.
20. (v2.0) Run configuration UI: modal dialog exposing suite, chaos profile, ADK toggle, and forensic toggle.
21. (v2.0) Artifact export/download: browser-side download for report JSON and trace JSONL from report, replay, and run-detail views.

### Deferred
1. Full model abstraction layer for multi-provider benchmark execution.
2. Full memory architecture beyond deterministic local benchmark requirements.
3. Full protocol-level A2A feature parity from the long spec.

### Dropped (for v1-v2 horizon)
1. No separate standalone A2A broker service in near-term versions; registry-hosted relay remains the v1-v2 default.

## Versioned Closure Plan

### v1.2 Closure Targets (ALL CLOSED)
1. ✅ Update architecture docs to match actual service topology and benchmark runtime shape. — `SERVICES.md`, `AGENTS.md`, `EVALUATION.md` reconciled with implementation.
2. ✅ Add front desk ILL delegation path as an ADK sub-agent workflow and test it. — `ILLEscalationAgent` created, `FrontDeskAgent` updated with ILL tool + sub-agent + fallback routing; 6 tests passing.
3. ✅ Implement/enforce minimum outbound security validation for A2A payloads in benchmark-critical paths. — `PROHIBITED_PAYLOAD_FIELDS` + `_validate_outbound_payload()` in `a2a_client.py`; 9 tests passing. PII canary scanner + null-content trap evaluator + compliance report generator added.
4. ✅ Record memory-system scope decision: session memory only for v1.x gates. — Documented in `PROJECT_STATUS.md` and drift matrix.

### v1.3 Closure Targets (ALL CLOSED)
1. ✅ Productionize A2A behavior semantics (timeouts, retries, late/duplicate handling) and document them as canonical. — `services/ill/src/ill/resilience.py` (async_retry with jitter), `services/registry/src/registry/a2a_relay.py` (dedup), `docs/architecture/A2A_PROTOCOL.md` (MVP relay semantics section).
2. ✅ Add resilience/chaos contract to architecture docs and benchmark scoring. — `scripts/chaos_profiles.py`, `scripts/chaos_controller.py`, `scripts/resilience_evaluator.py`; benchmark report schema 1.3 includes `chaos_summary` and `resilience_summary`; 28 new chaos/resilience tests passing.
3. ✅ Burn down noisy warnings that hide signal in CI and local runs. — All ~30 `datetime.utcnow()` usages replaced with `datetime.now(timezone.utc)` across 7 files; 0 remaining matches.

### v1.4 Closure Targets (ALL CLOSED)
1. ✅ Establish deterministic federated hub/spoke seed topology with manifest-driven ownership mapping. — `data/network_seed_manifest.json`, `scripts/seed_manifest_validator.py`, `scripts/seed_network.py`; 12 manifest tests passing.
2. ✅ Align registry partner-library records with seeded remote holdings references. — tusk-conservatory added to `conftest.py` registry_client and `routes.py` KNOWN_SOURCE_LIBRARIES; all 4 spoke libraries seeded with specializations.
3. ✅ Validate local-miss/network-hit ILL behavior against seeded federated datasets. — 8 ILL federation tests including full lifecycle with A2A notification; `_is_known_local_book()` extracted for monkeypatch override.

### v1.5 Closure Targets (ALL CLOSED)
1. ✅ Replace latest-artifact-only behavior with run-scoped artifact lifecycle (`run_id` control plane). — `agents/src/agents/run_index.py` (RunIndexManager with atomic JSON persistence), `agents/src/agents/benchmark_orchestrator.py` (async lifecycle management); 10 run index integrity tests passing.
2. ✅ Expose benchmark orchestration endpoints for create/list/get/report/trace by run. — `agents/src/agents/api.py` (7 new routes: POST/GET /benchmark/runs, GET /runs/{run_id}, /report, /trace, /artifacts); 13 lifecycle integration tests passing.
3. ✅ Preserve backward compatibility for existing benchmark artifact readers. — `GET /benchmark/report` uses two-tier resolution (latest successful run first, flat file fallback); `scripts/benchmark_run.py` without `--run-id` writes to flat `artifacts/` with schema "1.3" unchanged.

### v1.6 Closure Targets
1. Move operator UX from single-shell layout to route-based run/report/replay navigation.
2. Add CI validation for operator routes and frontend E2E smoke.
3. Provide local preflight/start command path with deterministic diagnostics.

### v1.7 Closure Targets
1. Upgrade fixture-based federation to live service federation with real HTTP resolution.
2. Add multi-tenant `library_code` to catalog service for spoke holdings.
3. Validate full ILL lifecycle through live services with A2A message verification.

### v1.7.5 Closure Targets (ALL CLOSED)
1. ✅ Establish ADR and architecture-decision governance as CI-enforced repo policy. — `docs/architecture/adr/` (README, template, index, 3 retroactive ADRs), `scripts/check_adr_links.py` (6 checks, CI gate).
2. ✅ Define API/artifact compatibility policy with executable contract tests. — `docs/development/CONTRACT_COMPATIBILITY_POLICY.md`, 3 golden fixtures under `tests/fixtures/golden/`, `tests/scenarios/test_contract_compatibility.py` (6 tests, CI gate).
3. ✅ Enforce dependency boundaries across agents/services/shared modules. — `docs/development/DEPENDENCY_BOUNDARY_MAP.md`, `scripts/check_dependency_boundaries.py` (AST-based, 74 files scanned, 0 violations, CI gate), `tests/scenarios/test_dependency_boundaries.py` (5 tests).

### v1.8 Closure Targets (ALL CLOSED)
1. ✅ Enforce service-trust/auth checks for benchmark-critical inter-service paths. — `shared/src/shared/auth.py` (ServiceAuthMiddleware), all 5 services enforce X-Service-Token, `shared/src/shared/http_client.py` auto-injects token; 10 trust tests passing.
2. ✅ Standardize observability schema and correlation IDs across run lifecycle flows. — `shared/src/shared/observability.py` (StructuredLogEvent, RequestCorrelationMiddleware, ContextVar propagation), X-Request-ID/X-Run-ID forwarded in outbound calls; 8 observability tests passing.
3. ✅ Validate reliability controls (timeouts/retries/circuit behavior) under deterministic tests. — `docs/architecture/adr/ADR-004-reliability-policy.md`, `scripts/check_resilience_policy.py` (AST-based, 0 violations); 8 reliability tests passing.

### v1.8.5 Closure Targets (ALL CLOSED)
1. ✅ Codify performance budgets for local alpha workflows and enforce them in CI. — `docs/development/PERFORMANCE_BUDGETS.md`, `scripts/perf_smoke.py` (PerformanceSmokeRunner), `tests/scenarios/test_performance_budgets.py` (8 tests).
2. ✅ Validate backup/restore and rollback drills for run artifacts and seeded datasets. — `docs/development/RECOVERY_AND_ROLLBACK_RUNBOOK.md`, `scripts/recovery_drill.py` (RecoveryDrillRunner with SHA256 verification), `tests/scenarios/test_recovery_drill.py` (10 tests).
3. ✅ Automate a release-candidate gate that aggregates all blocking readiness checks. — `scripts/release_gate_v2_0_rc.py` (7-gate ReleaseGateRunner), `tests/scenarios/test_release_gate_report_schema.py` (14 tests), `.github/workflows/ci.yml` (1 new CI step).

### v2.0 Closure Targets (ALL CLOSED)
1. ✅ Deliver local operator UI for configure -> run -> replay -> export. — Run config dialog (`run-config-dialog.component.ts`), artifact export buttons on report/replay/run-detail views, browser-side download utility.
2. ✅ Integrate pre-v2 architecture, security, and release gates into end-to-end operator workflows. — Release gate minimum raised to 620, all 7 gates passing.
3. ✅ Validate model/memory contracts in UI-driven local alpha use without reopening deferred architecture scope. — `ADR-005-single-provider-model-contract.md`, `ADR-006-session-only-memory-contract.md`, `tests/scenarios/test_model_memory_contract.py` (8 tests).

## Acceptance Checks for Drift Closure
1. ✅ Architecture docs no longer contradict live service topology or endpoint semantics.
2. ✅ Front desk can route ILL escalation path through deterministic test coverage.
3. ✅ A2A behavior semantics in docs and tests match one another.
4. ✅ `uv run pytest -q` remains green while drift closures land. (624 passed, 6 skipped, 10 xfailed)

## References
- `docs/architecture/OVERVIEW.md`
- `docs/architecture/SERVICES.md`
- `docs/architecture/AGENTS.md`
- `docs/architecture/A2A_PROTOCOL.md`
- `docs/architecture/EVALUATION.md`
- `docs/architecture/SECURITY.md`
- `docs/architecture/MODEL_ABSTRACTION.md`
- `docs/architecture/MEMORY_SYSTEM.md`
- `docs/status/VERSION_LADDER_PROPOSAL.md`
- `docs/status/V1_2_EXECUTION_PLAN.md`
- `docs/status/V1_3_EXECUTION_PLAN.md`
- `docs/status/V1_4_EXECUTION_PLAN.md`
- `docs/status/V1_5_EXECUTION_PLAN.md`
- `docs/status/V1_6_EXECUTION_PLAN.md`
- `docs/status/V1_7_EXECUTION_PLAN.md`
- `docs/status/V1_7_5_EXECUTION_PLAN.md`
- `docs/status/V1_8_EXECUTION_PLAN.md`
- `docs/status/V1_8_5_EXECUTION_PLAN.md`
- `docs/status/V2_0_EXECUTION_PLAN.md`
