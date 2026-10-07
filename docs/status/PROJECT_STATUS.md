# Project Status Dashboard

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Single source of truth for project-wide status and next steps
- Source of Truth: This file
- Supersedes: `README.md` phase blocks, `CATALOG_STATUS.md`, `PHASE_1.5_COMPLETE.md`, `TEST_IMPLEMENTATION_SUMMARY.md`, `docs/development/NEXT_STEPS.md`
- Related Workstream: infrastructure-services

## Global Phase Table

| Area | Status | Evidence |
|---|---|---|
| Core services (catalog/circulation/ill/registry) | Implemented | `services/*/src/*/main.py`, `docker-compose.yml` |
| ADK agents | Implemented | `agents/src/agents/*.py`, `agents/src/agents/benchmark_runner.py`, `agents/tests/integration/test_benchmark_runner.py` |
| MCP tooling | Implemented | `services/*/src/*/mcp_server.py` |
| A2A runtime interop | Implemented | `services/registry/src/registry/a2a_relay.py`, `services/ill/src/ill/a2a_client.py`, `services/ill/tests/integration/test_a2a_happy_path.py`, `services/ill/tests/integration/test_a2a_denial_path.py` |
| Evaluation harness | Implemented | `tests/scenarios/test_tier1_catalog.py`, `tests/scenarios/test_tier2_circulation.py`, `tests/scenarios/test_tier3_ill_a2a.py`, `scripts/benchmark_run.py` |
| World/data governance | Implemented | `data/*.json`, `tests/scenarios/test_synthetic_guardrails.py`, `docs/world/*.md` |

## Verified Snapshot (2026-02-08)
- ADK + MCP: implemented in code.
- A2A: specification exists and runtime MVP relay path is now implemented for ILL handoff.
- Test health: stabilized for current scope; full suite now passes.

## Verified Snapshot (2026-02-09)
- A2A runtime now includes denial/late-message handling, retry timeout behavior, and relay ack idempotency coverage.
- Tier 1-3 deterministic scenario suite runs in-process with no external service/API-key dependency.
- Benchmark artifacts are manifest-driven with explicit per-scenario v1 metrics and taxonomy fields.
- Reproducible benchmark path is available via `scripts/run_benchmark_v1.sh` and CI artifact publishing.

### Evidence Commands
```bash
uv run pytest -q
rg -n "google.adk|LlmAgent" agents/src
rg -n "FastMCP|@mcp.tool|@mcp.resource" services/*/src/*/mcp_server.py
rg -n "A2A|a2a|message/send" docs/architecture services/ill/src services/registry/src
```

## Current Sprint Outcomes (A2A MVP + Thin Scorer)
- Implemented registry-hosted A2A relay endpoints:
  - `POST /a2a/message/send`
  - `GET /a2a/messages/{library_code}`
  - `POST /a2a/messages/{message_id}/ack`
- Implemented ILL A2A client and inbound callback handling:
  - `services/ill/src/ill/a2a_client.py`
  - `POST /a2a/inbound`
- Added deterministic end-to-end A2A happy-path test:
  - `services/ill/tests/integration/test_a2a_happy_path.py`
- Added thin benchmark scorer and taxonomy artifacts:
  - `scripts/benchmark_run.py`
  - `scripts/benchmark_taxonomy.py`
  - Artifacts: `artifacts/benchmark-report.json`, `artifacts/benchmark-report.md`
- Added baseline CI workflow:
  - `.github/workflows/ci.yml`

## v1 Closeout Sprint Outcomes (A2A + Harness + Scoring)
- Added A2A denial and retry coverage:
  - `services/ill/tests/integration/test_a2a_denial_path.py`
  - `services/ill/tests/integration/test_a2a_retry_timeout.py`
  - `services/registry/tests/unit/test_a2a_relay_idempotency.py`
- Added deterministic Tier 1-3 scenario files and no-skip guard:
  - `tests/scenarios/test_tier1_catalog.py`
  - `tests/scenarios/test_tier2_circulation.py`
  - `tests/scenarios/test_tier3_ill_a2a.py`
  - `tests/scenarios/test_v1_scenarios_no_skip.py`
- Added manifest-driven scoring contract and validation:
  - `tests/scenarios/scenario_manifest.json`
  - `tests/scenarios/test_benchmark_scoring.py`
  - `scripts/benchmark_run.py`
  - `scripts/benchmark_taxonomy.py`
- Added deterministic ADK benchmark runner and tests:
  - `agents/src/agents/benchmark_runner.py`
  - `agents/tests/integration/test_benchmark_runner.py`
- Added benchmark runbook and one-command execution wrapper:
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `scripts/run_benchmark_v1.sh`

## Test Stabilization Snapshot (2026-02-09)
- Collection conflicts resolved using importlib mode and test package cleanup.
- Catalog, circulation, ILL, and agent suites pass in current baseline.
- Scenario guardrails enforce synthetic-only references.
- Baseline command result:
  - `uv run pytest -q` -> `413 passed, 6 skipped, 10 xfailed`
- Detailed execution tracker:
  - `docs/status/TEST_STABILIZATION_CHECKLIST.md`

## v1.1 Forensic Judge Foundations (2026-02-09)
- Implemented canonical trace contract:
  - `shared/src/shared/eval/trace_schemas.py` — TraceEvent, TraceSummary, ForensicAssertionResult Pydantic models
  - `shared/src/shared/eval/trace_writer.py` — JSONL trace writer
  - `artifacts/benchmark-trace.jsonl` — emitted on every benchmark run
- Implemented SQL forensic assertions:
  - `scripts/forensic_sql.py` — `inventory_conservation_v1` and `financial_integrity_v1` assertion definitions
  - `scripts/forensic_assertions.py` — ForensicAssertionRunner module
  - `artifacts/forensic-assertions.json` — assertion results with SQL evidence
- Added file-backed DB support in scenario fixtures:
  - `tests/scenarios/conftest.py` — `_make_engine()` with `BENCHMARK_DB_DIR` env var
- Bumped benchmark report schema to v1.1:
  - `scripts/benchmark_run.py` — `schema_version: "1.1"`, `trace_summary`, `forensic_assertions`
- Added ADK trace emission:
  - `agents/src/agents/benchmark_runner.py` — optional TraceWriter integration
- Added v1.1 tests:
  - `tests/scenarios/test_trace_schema.py` (8 tests)
  - `tests/scenarios/test_forensic_assertions.py` (12 tests)
  - `tests/scenarios/test_benchmark_scoring.py` (2 new v1.1 schema validation tests)
- Updated CI and runbook:
  - `.github/workflows/ci.yml` — trace and forensic assertion test steps
  - `docs/development/BENCHMARK_RUNBOOK.md` — v1.1 artifact contract and troubleshooting
  - `scripts/run_benchmark_v1.sh` — v1.1 verification steps

### v1.1 Evidence Commands
```bash
uv run pytest tests/scenarios/test_trace_schema.py -q
uv run pytest tests/scenarios/test_forensic_assertions.py -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.2 Safety and Red-Team Packs (2026-02-08)
- Implemented null-content trap pack:
  - `data/null_content_trap_cases.json` — 10 anti-fabrication trap cases
  - `scripts/safety_evaluator.py` — NullContentEvaluator (deterministic string matching)
  - `tests/scenarios/test_null_content_trap.py` (9 tests)
- Implemented honey pot PII red-team pack:
  - `data/canary_pii_profiles.json` — 3 canary profiles, 8 attack scenarios
  - `scripts/pii_canary_scanner.py` — PIICanaryScanner (canary token detection)
  - `tests/scenarios/test_honey_pot_redteam.py` (13 tests)
- Implemented compliance report generator:
  - `scripts/compliance_report.py` — JSON + Markdown compliance artifacts
  - `tests/scenarios/test_compliance_report_schema.py` (8 tests)
  - `tests/scenarios/test_safety_pack_scoring.py` (4 tests)
- Closed architecture drift items:
  - Front desk ILL delegation via `agents/src/agents/ill_escalation_agent.py`
  - ILL tools: `agents/src/agents/tools/ill_tools.py`
  - A2A payload validation: `services/ill/src/ill/a2a_client.py` (PROHIBITED_PAYLOAD_FIELDS)
  - `agents/tests/unit/test_front_desk_ill_delegation.py` (6 tests)
  - `services/ill/tests/unit/test_a2a_payload_validation.py` (9 tests)
- Bumped benchmark report schema to v1.2:
  - `scripts/benchmark_run.py` — schema_version 1.2, safety_summary, null_content_results, pii_leakage_results
  - New taxonomy categories: content_fabrication, pii_leakage
  - New trace event types: SAFETY_CHECK_START, SAFETY_CHECK_RESULT
- Updated benchmark wrapper: `scripts/run_benchmark_v1.sh` with v1.2 safety steps
- Test baseline: `uv run pytest -q` -> `456 passed, 6 skipped, 10 xfailed`

### v1.2 Evidence Commands
```bash
uv run pytest tests/scenarios/test_null_content_trap.py -q
uv run pytest tests/scenarios/test_honey_pot_redteam.py -q
uv run pytest tests/scenarios/test_compliance_report_schema.py -q
uv run pytest tests/scenarios/test_safety_pack_scoring.py -q
uv run pytest agents/tests -q
uv run pytest services/ill/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.3 Chaos & Resilience + A2A Productionization (2026-02-09)
- Implemented deterministic chaos testing framework:
  - `scripts/chaos_profiles.py` — FaultType enum, FaultProfile schema, 4 built-in profiles
  - `scripts/chaos_controller.py` — ChaosController with deterministic call-index fault injection
  - `tests/scenarios/test_chaos_fault_injection.py` (13 chaos controller unit tests)
- Implemented resilience scoring and chaos report generation:
  - `scripts/resilience_evaluator.py` — ResilienceEvaluator (weighted composite scoring), ChaosReport
  - `tests/scenarios/test_resilience_scoring.py` (7 tests)
  - `tests/scenarios/test_chaos_report_schema.py` (4 tests)
- Implemented chaos integration scenarios:
  - `tests/scenarios/test_tier3_ill_a2a_chaos.py` (4 chaos scenarios: timeout recovery, 500 degradation, malformed response, intermittent outage)
  - `tests/scenarios/conftest.py` — chaos_controller, chaotic_ill_client, chaotic_catalog_client fixtures
- Hardened A2A relay and ILL retry:
  - `services/ill/src/ill/resilience.py` — lightweight async_retry with jitter (ILL-local)
  - `services/ill/src/ill/a2a_client.py` — refactored to use @async_retry decorator
  - `services/registry/src/registry/a2a_relay.py` — message dedup via _seen_ids
  - `services/registry/src/registry/routes.py` — dedup response (status: queued|duplicate)
  - `services/ill/tests/integration/test_a2a_retry_timeout.py` (+2 jitter/backoff tests)
  - `services/registry/tests/unit/test_a2a_relay_idempotency.py` (+2 dedup tests)
- Warning burn-down: replaced all ~30 `datetime.utcnow()` usages with `datetime.now(timezone.utc)` across 7 files
- Bumped benchmark report schema to v1.3:
  - `scripts/benchmark_run.py` — schema_version 1.3, chaos_summary, resilience_summary, --chaos-profile CLI
  - New taxonomy categories: resilience_failure, timeout_exhaustion
  - New trace event types: CHAOS_FAULT_INJECTED, CHAOS_RECOVERY_ATTEMPT, RESILIENCE_SCORE_COMPUTED
- Updated benchmark wrapper: `scripts/run_benchmark_v1.sh` with v1.3 chaos steps
- Updated scenario manifest: `tests/scenarios/scenario_manifest.json` bumped to v1.3 with 4 chaos scenarios
- Test baseline: `uv run pytest -q` -> `488 passed, 6 skipped, 10 xfailed`

### v1.3 Evidence Commands
```bash
uv run pytest tests/scenarios/test_chaos_fault_injection.py -q
uv run pytest tests/scenarios/test_resilience_scoring.py -q
uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q
uv run pytest tests/scenarios/test_chaos_report_schema.py -q
uv run pytest services/ill/tests -q
uv run pytest services/registry/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.4 Federated Data Topology (2026-02-09)
- Implemented deterministic federated hub/spoke seed topology:
  - `data/network_seed_manifest.json` — canonical batch-to-library ownership map (schema 1.4)
  - `scripts/seed_manifest_validator.py` — ManifestValidator (8 checks: schema, coverage, counts, duplicates, spoke codes, totals)
  - `scripts/seed_network.py` — federated seed orchestrator with validation + report generation
  - `scripts/seed_all.py` — added `--federated` flag for network seed mode
- Implemented spoke holdings fixtures and partitioning verification:
  - `tests/scenarios/conftest.py` — spoke_holdings (session-scoped), federated_ill_client (monkeypatched), tusk-conservatory registry entry
  - `tests/scenarios/test_federated_seed_manifest.py` (12 tests)
  - `tests/scenarios/test_federated_catalog_partitioning.py` (9 tests)
- Implemented ILL federation scenarios proving local-miss/network-hit behavior:
  - `services/ill/src/ill/routes.py` — tusk-conservatory added to KNOWN_SOURCE_LIBRARIES; `_is_known_local_book()` extracted for monkeypatch override
  - `tests/scenarios/test_ill_network_holdings_resolution.py` (8 tests: spoke request creation, holdings query resolution, cross-spoke overlap, full lifecycle with A2A notification, genre-specialization alignment)
- Updated benchmark infrastructure:
  - `tests/scenarios/scenario_manifest.json` — bumped to v1.4, added 6 federated scenarios
  - `scripts/benchmark_run.py` — ManifestScenario extended with `requires_federated_seed`, `expected_source_library`, `network_lookup_required`
  - `tests/scenarios/test_v1_scenarios_no_skip.py` — added 3 new test files to guard list
- Test baseline: `uv run pytest -q` -> `517 passed, 6 skipped, 10 xfailed`

### v1.4 Evidence Commands
```bash
uv run pytest tests/scenarios/test_federated_seed_manifest.py -q
uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q
uv run python scripts/seed_manifest_validator.py --check-only
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.5 Run Control Plane (2026-02-09)
- Implemented run metadata models and run index persistence:
  - `agents/src/agents/benchmark_api_models.py` — RunStatus, RunMetadata, RunIndex, RunCreateRequest/Response, RunListResponse
  - `agents/src/agents/run_index.py` — RunIndexManager with atomic JSON persistence (fcntl file locking)
  - `agents/tests/integration/test_run_index_integrity.py` (10 tests)
- Implemented async benchmark orchestration API:
  - `agents/src/agents/benchmark_orchestrator.py` — BenchmarkOrchestrator with asyncio.create_task subprocess execution
  - `agents/src/agents/api.py` — 7 new routes (POST/GET /benchmark/runs, GET /runs/{run_id}, /report, /trace, /artifacts)
  - `agents/tests/integration/test_benchmark_run_lifecycle.py` (13 tests)
- Updated legacy `/benchmark/report` endpoint with two-tier resolution (latest successful run first, flat file fallback)
- Updated benchmark runner for run-scoped output:
  - `scripts/benchmark_run.py` — added `--run-id` arg, run_id passthrough to TraceWriter, conditional schema version bump to "1.5"
  - `scripts/run_benchmark_v1.sh` — v1.5 version labels, run control plane test steps, run index verification
  - `agents/tests/integration/test_benchmark_runner.py` — 2 new TraceWriter run_id tests
- Test baseline: `uv run pytest -q` -> `517 passed, 6 skipped, 10 xfailed` (scenario baseline unchanged; +25 agent tests: 145 total)

### v1.5 Evidence Commands
```bash
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
uv run pytest agents/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.6 Operator Surface Hardening (2026-02-09)
- Implemented Angular route-based navigation (hash routing):
  - `frontend/src/app/app.routes.ts` — 5 routes + wildcard redirect to `/chat`
  - `frontend/src/app/app.config.ts` — `provideRouter(routes, withHashLocation())`
  - `frontend/src/app/app.component.ts` — nav bar shell + `<router-outlet>`
- Implemented chat page wrapper:
  - `frontend/src/app/features/chat-page/chat-page.component.ts` — lift-and-shift of 3-panel layout
- Implemented operator views:
  - `frontend/src/app/features/runs/run-list.component.ts` — run table with status badges, create run, navigate to detail
  - `frontend/src/app/features/run-detail/run-detail.component.ts` — metadata, status polling, action links, artifacts
  - `frontend/src/app/features/reports/report-view.component.ts` — metrics grid, scenario table, forensic assertions
  - `frontend/src/app/features/replay/replay-view.component.ts` — trace event timeline with color-coded markers
- Implemented RunService for V1.5 API consumption:
  - `frontend/src/app/core/services/run.service.ts` — 7 methods (CRUD + polling)
  - `frontend/src/app/shared/models/benchmark.models.ts` — V1.5 TypeScript interfaces
- Wired "Commence Benchmark" in ScenarioSidebar to RunService.createRun()
- Added `loadRunReport(runId)` to BenchmarkService
- Implemented Playwright E2E coverage:
  - `frontend/e2e/chat-smoke.spec.ts` — updated for routed app (4 tests)
  - `frontend/e2e/run-orchestration.spec.ts` — run routes and creation (6 tests)
  - `frontend/e2e/report-replay.spec.ts` — report/replay views (5 tests)
- Created local preflight script:
  - `scripts/run_local_alpha.sh` — prerequisite, port, and health checks

### v1.6 Evidence Commands
```bash
cd frontend && ng build
cd frontend && npm run e2e
scripts/run_local_alpha.sh
```

## v1.7 Multi-Instance Federated Catalogs (2026-02-09)
- Implemented multi-instance catalog federation (Option B — one service per library):
  - `services/catalog/src/catalog/routes.py` — LIBRARY_CODE/LIBRARY_NAME env vars, `/library/info` endpoint
  - `services/catalog/src/catalog/schemas.py` — LibraryInfoResponse model, library_code in HealthResponse
  - `services/catalog/src/catalog/main.py` — dynamic FastAPI title from env var
- Implemented spoke catalog seeder and provisioner:
  - `scripts/seed_spoke_catalog.py` — CLI seeder: reads manifest, seeds individual library catalog DB with books + instances
  - `scripts/seed_network.py` — added `--mode provision` for per-library SQLite DB provisioning
  - Library-specific barcode prefixes: HAN, MAS, MAM, IVY, TUS
- Implemented direct URL HTTP client for spoke resolution:
  - `shared/src/shared/http_client.py` — `call_url()` and `call_remote_catalog()` for explicit URL calls
- Implemented registry federation seeding:
  - `scripts/seed_registry_federation.py` — registers spoke libraries with catalog_url in registry
  - `services/registry/src/registry/schemas.py` — `catalog_url` field on PartnerLibraryCreate/Update/Response
  - `services/registry/src/registry/routes.py` — catalog_url wired through all CRUD paths
  - `data/network_seed_manifest.json` — added `endpoints` section with port/docker_host per library
- Implemented ILL live spoke verification:
  - `services/ill/src/ill/routes.py` — Step 3b: look up catalog_url from registry, verify spoke holds ISBN before ILL creation
  - `services/ill/src/ill/schemas.py` — added optional `isbn` field to ILLRequestCreate
  - Graceful degradation: if spoke unreachable, proceeds with warning
- Implemented live federation test infrastructure:
  - `tests/scenarios/conftest.py` — `live_spoke_catalogs` (per-spoke in-memory ASGI apps) and `live_federation_client` fixtures
  - `tests/scenarios/test_spoke_catalog_seeding.py` (11 tests: book counts, instances, no overlap, barcode prefixes)
  - `tests/scenarios/test_registry_spoke_resolution.py` (8 tests: call_url GET/POST, errors, delegation)
  - `tests/scenarios/test_live_federation.py` (11 tests: spoke direct query, ILL with live verification, cross-spoke, graceful degradation)
- Implemented Docker multi-instance federation:
  - `docker-compose.yml` — 4 spoke catalog services (catalog-mastodon:8011, catalog-mammoth:8012, catalog-ivory:8013, catalog-tusk:8014), 4 new volumes
  - `scripts/seed_docker_federation.sh` — Docker federation seed script (health wait, spoke seed, registry seed, smoke test)
- Test baseline: `uv run pytest -q` -> `547 passed, 6 skipped, 10 xfailed` (+30 from v1.6)

### v1.7 Evidence Commands
```bash
uv run pytest tests/scenarios/test_spoke_catalog_seeding.py -q
uv run pytest tests/scenarios/test_registry_spoke_resolution.py -q
uv run pytest tests/scenarios/test_live_federation.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q  # v1.4 backward compat
docker compose up --build -d && bash scripts/seed_docker_federation.sh     # Docker federation
```

## v1.7.5 Architecture Contract Gates (2026-02-09)
- Implemented ADR governance baseline:
  - `docs/architecture/adr/README.md` — ADR governance guide and conventions
  - `docs/architecture/adr/ADR_TEMPLATE.md` — decision record template
  - `docs/architecture/adr/INDEX.md` — master ADR index (3 retroactive entries)
  - `docs/architecture/adr/ADR-001-multi-instance-federation.md` — v1.7 Option B decision
  - `docs/architecture/adr/ADR-002-registry-hosted-a2a-relay.md` — A2A relay hosting decision
  - `docs/architecture/adr/ADR-003-pytest-manifest-benchmark-engine.md` — eval engine decision
  - `scripts/check_adr_links.py` — ADR link/section validator (6 checks)
- Implemented API/schema compatibility policy:
  - `docs/development/CONTRACT_COMPATIBILITY_POLICY.md` — schema versioning and compatibility rules
  - `tests/fixtures/golden/benchmark-report-v1.1.json` — golden report fixture
  - `tests/fixtures/golden/run-index-v1.5.json` — golden run index fixture
  - `tests/fixtures/golden/scenario-manifest-v1.4.json` — golden manifest fixture
  - `tests/scenarios/test_contract_compatibility.py` (6 tests)
- Implemented dependency boundary enforcement:
  - `docs/development/DEPENDENCY_BOUNDARY_MAP.md` — import DAG and boundary rules
  - `scripts/check_dependency_boundaries.py` — AST-based boundary checker (74 files scanned, 0 violations)
  - `tests/scenarios/test_dependency_boundaries.py` (5 tests)
- Added 3 new CI gates: ADR governance, contract compatibility, dependency boundaries
- Test baseline: `uv run pytest -q` -> `558 passed, 6 skipped, 10 xfailed` (+11 from v1.7)

### v1.7.5 Evidence Commands
```bash
uv run python scripts/check_adr_links.py --strict
uv run pytest tests/scenarios/test_contract_compatibility.py -q
uv run python scripts/check_dependency_boundaries.py --strict
uv run pytest tests/scenarios/test_dependency_boundaries.py -q
```

## v1.8 Security and Operability Foundations (2026-02-09)
- Implemented service trust baseline (shared-secret auth):
  - `shared/src/shared/auth.py` — `get_service_token()`, `ServiceAuthMiddleware(BaseHTTPMiddleware)`, `SERVICE_TOKEN_HEADER`
  - Auth middleware added to all 5 services (catalog, circulation, ill, registry, agents)
  - `shared/src/shared/http_client.py` — auto-injects `X-Service-Token` in `call_service()` and `call_url()`
  - Agent tools (`catalog_tools.py`, `circulation_tools.py`, `ill_tools.py`) — auth headers on all httpx calls
  - `tests/scenarios/test_service_trust.py` (10 tests: rejection, acceptance, public paths, invalid tokens)
- Implemented observability contract (correlation IDs + structured log schema):
  - `shared/src/shared/observability.py` — `StructuredLogEvent`, `RequestCorrelationMiddleware`, `correlation_id_var`/`run_id_var` ContextVars
  - Correlation middleware added to all 5 services (X-Request-ID generation/echo, X-Run-ID propagation)
  - `shared/src/shared/http_client.py` — auto-forwards correlation + run ID headers in outbound calls
  - `tests/fixtures/golden/structured-log-event-v1.8.json` — golden fixture for log event schema
  - `tests/scenarios/test_observability_contract.py` (8 tests: schema validation, golden fixture, correlation header behavior)
- Implemented reliability controls (ADR-004 + checker + tests):
  - `docs/architecture/adr/ADR-004-reliability-policy.md` — codified reliability defaults (10s timeout, 3 retries, CB thresholds)
  - `scripts/check_resilience_policy.py` — AST-based checker: agents tool functions using httpx.AsyncClient must have @with_retry
  - `tests/scenarios/test_reliability_policy.py` (8 tests: timeout defaults, retry behavior, circuit breaker transitions, health endpoints)
- Updated CI with 2 new gates: resilience policy check, combined trust/observability/reliability test step
- Updated environment: `SERVICE_AUTH_TOKEN` in `.env.example` and all `docker-compose.yml` service blocks
- Test baseline: `uv run pytest -q` -> `584 passed, 6 skipped, 10 xfailed` (+26 from v1.7.5)

### v1.8 Evidence Commands
```bash
uv run pytest tests/scenarios/test_service_trust.py -q
uv run pytest tests/scenarios/test_observability_contract.py -q
uv run pytest tests/scenarios/test_reliability_policy.py -q
uv run python scripts/check_resilience_policy.py --strict
uv run python scripts/check_adr_links.py --strict
```

## v1.8.5 Release Candidate Hardening (2026-02-09)
- Implemented performance budget enforcement:
  - `docs/development/PERFORMANCE_BUDGETS.md` — budget thresholds (health < 2s, smoke total < 10s, report < 5s)
  - `scripts/perf_smoke.py` — PerformanceSmokeRunner with in-process ASGI health checks, report generation timing, JSON report output
  - `tests/scenarios/test_performance_budgets.py` (8 tests: doc presence, threshold validation, script structure, smoke execution, report schema)
- Implemented recoverability and rollback drills:
  - `docs/development/RECOVERY_AND_ROLLBACK_RUNBOOK.md` — backup/restore/verify procedures for run artifacts
  - `scripts/recovery_drill.py` — RecoveryDrillRunner with backup/restore/verify/drill subcommands, SHA256 checksum verification
  - `tests/scenarios/test_recovery_drill.py` (10 tests: runbook, script structure, backup/restore/verify operations)
- Implemented release gate automation:
  - `scripts/release_gate_v2_0_rc.py` — ReleaseGateRunner aggregating 7 gates (ADR, boundaries, resilience, perf, recovery, test count, frontend), JSON + Markdown report output
  - `tests/scenarios/test_release_gate_report_schema.py` (14 tests: script structure, report schema, status logic, report generation, runner behavior)
  - `.github/workflows/ci.yml` — added release gate CI step
- Test baseline: `uv run pytest -q` -> `616 passed, 6 skipped, 10 xfailed` (+32 from v1.8)

### v1.8.5 Evidence Commands
```bash
uv run pytest tests/scenarios/test_performance_budgets.py -q
uv run pytest tests/scenarios/test_recovery_drill.py -q
uv run pytest tests/scenarios/test_release_gate_report_schema.py -q
uv run python scripts/perf_smoke.py --strict
uv run python scripts/release_gate_v2_0_rc.py --strict --skip-frontend
```

## v2.0 Local Hosted Alpha (2026-02-09)
- Implemented architecture contract closure (model + memory):
  - `docs/architecture/adr/ADR-005-single-provider-model-contract.md` — Gemini-only model contract for v2.0
  - `docs/architecture/adr/ADR-006-session-only-memory-contract.md` — session-only memory contract for v2.0
  - `docs/architecture/adr/INDEX.md` — updated with ADR-005 and ADR-006
  - `tests/scenarios/test_model_memory_contract.py` (8 tests: model provider and memory contract enforcement)
- Implemented run configuration dialog:
  - `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts` — modal dialog exposing suite, chaos profile, ADK toggle, forensic toggle
  - `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts` — wired to open config dialog
  - `frontend/src/app/features/runs/run-list.component.ts` — wired to open config dialog
- Implemented artifact export/download:
  - `frontend/src/app/shared/utils/download.ts` — browser-side download utility (downloadJson, downloadText)
  - `frontend/src/app/features/reports/report-view.component.ts` — Export JSON button
  - `frontend/src/app/features/replay/replay-view.component.ts` — Export JSONL button
  - `frontend/src/app/features/run-detail/run-detail.component.ts` — Download Report/Trace buttons
- Updated release gate minimum test count to 620
- Test baseline: `uv run pytest -q` -> `624 passed, 6 skipped, 10 xfailed` (+8 from v1.8.5)

### v2.0 Evidence Commands
```bash
uv run pytest tests/scenarios/test_model_memory_contract.py -q
uv run python scripts/check_adr_links.py --strict
cd frontend && npx ng build
uv run python scripts/release_gate_v2_0_rc.py --strict --skip-frontend
uv run pytest -q
```

## v2.1 Run Comparison + Analytics + Assistant Live Execution (2026-02-10)
- Implemented model-aware run metadata and contracts:
  - `agents/src/agents/benchmark_api_models.py` — additive `model_name`/`model_family` in run request/response/index models
  - `agents/src/agents/benchmark_orchestrator.py` — run creation persists model metadata, benchmark subprocess receives per-run `MODEL_NAME`
- Implemented deterministic comparison and leaderboard APIs:
  - `agents/src/agents/benchmark_comparison.py` — composite score, run deltas, tier deltas, scenario deltas, deterministic leaderboard sort
  - `agents/src/agents/api.py` — `GET /benchmark/models`, `POST /benchmark/compare`, `GET /benchmark/leaderboard`
- Implemented analytics route and comparison UX:
  - `frontend/src/app/features/analytics/analytics.component.ts` — compare workbench + leaderboard + deep-link support
  - `frontend/src/app/app.routes.ts` — `/analytics` route
  - `frontend/src/app/features/runs/run-list.component.ts` — multi-select + Compare in Analytics action
  - `frontend/src/app/features/run-detail/run-detail.component.ts` — Compare CTA deep-link
  - `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts` — model selection from backend catalog
- Implemented role-aligned UX polish:
  - `frontend/src/app/core/layout/main-layout.component.ts` — dedicated Analytics nav + top-bar quick patron switch
  - Analytics remains available to evaluator patrons; patron directory stays staff-only.
- Implemented assistant scenario click-to-run loop:
  - `agents/src/agents/benchmark_api_models.py` — additive `scenario_ids` + `trigger_source` fields on run contracts
  - `agents/src/agents/api.py` — `POST /benchmark/runs` validation for scenario-scoped requests (suite guard + unknown id guard + dedupe)
  - `agents/src/agents/benchmark_orchestrator.py` — forwards repeated `--scenario-id` args to runner
  - `scripts/benchmark_run.py` — scenario-id CLI filtering via deterministic pytest `-k` expression and `selected_scenario_ids` report/trace metadata
- Implemented live assistant audit stream wiring:
  - `frontend/src/app/core/services/assistant-run.service.ts` — active run focus, run-status polling, live trace polling, script trigger stream
  - `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts` — scenario card `select + run immediately` with per-card run status
  - `frontend/src/app/features/chat/chat.component.ts` — run-triggered chat reset + script replay
  - `frontend/src/app/shared/utils/audit-trace.mapper.ts` — shared trace-event-to-audit-entry mapping
  - `frontend/src/app/features/forensic-ledger/forensic-ledger.component.ts` — live event rendering + `Open Run Detail` deep-link
- Added/updated `v2.1` tests:
  - `agents/tests/integration/test_benchmark_run_lifecycle.py`
  - `agents/tests/integration/test_run_index_integrity.py`
  - `tests/scenarios/test_contract_compatibility.py`
  - `frontend/e2e/analytics.spec.ts`
  - `frontend/e2e/assistant-scenario-run.spec.ts`
  - `frontend/e2e/chat-smoke.spec.ts` (live-run override coverage)
- Documentation reconciliation:
  - `docs/status/V2_1_EXECUTION_PLAN.md` (new)
  - `docs/status/VERSION_LADDER_PROPOSAL.md` (updated `v2.1` status/footprint)
  - `docs/workstreams/*.md` (refreshed current reality + milestones)

### v2.1 Evidence Commands
```bash
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest tests/scenarios/test_contract_compatibility.py -q
cd frontend && npm run build
cd frontend && npm run e2e -- e2e/assistant-scenario-run.spec.ts
cd frontend && npm run e2e -- e2e/analytics.spec.ts
cd frontend && npm run e2e
```

## v2.1.2 Identity-Bound Assistant + v2.2 Prep Seams (2026-02-10)
- Implemented identity-bound chat contract:
  - `agents/src/agents/api.py` — `POST /chat` accepts `active_patron`, returns `bound_patron_id` + `session_rebound`
  - `agents/src/agents/chat.py` — identity-aware session resolution and mismatch rotation
  - `agents/src/agents/session/adk_session_service.py` — persisted patron id/name/role context fields
  - `agents/src/agents/session/active_patron_context.py` — request-scoped active patron context via `contextvars`
- Implemented active-profile account tooling:
  - `agents/src/agents/tools/circulation_tools.py` — self-tools (`get_my_patron_summary`, `get_my_fines`, `checkout_for_me`, `place_hold_for_me`) + cross-profile policy guard
  - `agents/src/agents/tools/ill_tools.py` — self-tools (`list_my_ill_requests`, `create_ill_request_for_me`) + cross-profile policy guard
  - `agents/src/agents/front_desk.py`, `agents/src/agents/circulation_agent.py`, `agents/src/agents/ill_escalation_agent.py` — active-profile-first prompt and fallback behavior
- Extended run observability identity:
  - `agents/src/agents/benchmark_api_models.py`, `agents/src/agents/benchmark_orchestrator.py`, `agents/src/agents/api.py` — additive `actor_patron_id` in run create/index response metadata
  - `frontend/src/app/core/services/assistant-run.service.ts` + `frontend/src/app/shared/models/benchmark.models.ts` — scenario-triggered runs include active `actor_patron_id`
- Implemented prompt-driven patron switch UX for chat contexts:
  - `frontend/src/app/core/layout/main-layout.component.ts`
  - `frontend/src/app/features/profile/patron-profile.component.ts`
  - `frontend/src/app/core/services/chat.service.ts` — always includes active patron payload and supports backend session rotation while preserving transcript
- Added v2.2-prep architecture closure artifacts:
  - `docs/architecture/adr/ADR-007-mcp-transport-strategy.md`
  - `docs/architecture/adr/ADR-008-agent-delegation-pattern.md`
  - `docs/architecture/adr/ADR-009-model-adapter-contract.md`
  - `docs/architecture/adr/INDEX.md` updated
  - `agents/src/agents/models/base.py`, `agents/src/agents/models/gemini_adapter.py`, `agents/src/agents/models/factory.py`
- Added/updated test coverage:
  - `agents/tests/integration/test_chat_identity_binding.py`
  - `agents/tests/integration/test_session_persistence.py`
  - `agents/tests/unit/test_active_patron_tools.py`
  - `agents/tests/integration/test_benchmark_run_lifecycle.py`
  - `agents/tests/integration/test_run_index_integrity.py`
  - `tests/scenarios/test_contract_compatibility.py`
  - `frontend/e2e/chat-identity.spec.ts`
  - `frontend/e2e/assistant-scenario-run.spec.ts`
  - `frontend/e2e/profile-account.spec.ts`
  - `frontend/e2e/analytics.spec.ts`
  - `frontend/e2e/chat-smoke.spec.ts`

### v2.1.2 Evidence Commands
```bash
uv run pytest agents/tests/integration/test_chat_identity_binding.py -q
uv run pytest agents/tests/integration/test_session_persistence.py -q
uv run pytest agents/tests/unit/test_active_patron_tools.py -q
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest tests/scenarios/test_contract_compatibility.py -q
cd frontend && npm run e2e -- e2e/chat-identity.spec.ts
cd frontend && npm run e2e -- e2e/assistant-scenario-run.spec.ts
cd frontend && npm run e2e
cd frontend && npm run build
```

## Next Steps by Workstream
- `docs/workstreams/infrastructure-services.md`
- `docs/workstreams/adk-agents.md`
- `docs/workstreams/a2a-network.md`
- `docs/workstreams/mcp-tooling.md`
- `docs/workstreams/evaluation-harness.md`
- `docs/workstreams/world-data-governance.md`

## Benchmark Completion References
- v1 Definition of Done and gap tracker:
  - `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md`
- Fully finished platform blueprint:
  - `docs/status/FULLY_FINISHED_TARGET_STATE.md`
- Versioned roadmap for post-v1 releases:
  - `docs/status/VERSION_LADDER_PROPOSAL.md`
- Architecture drift tracker:
  - `docs/status/ARCHITECTURE_DRIFT_REPORT.md`
- Active execution decomposition:
  - `docs/status/V1_1_EXECUTION_PLAN.md`
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
  - `docs/status/V2_1_EXECUTION_PLAN.md`

## Doc Reorg Report (2026-02-08)
- Canonical docs created:
  - `docs/README.md`
  - `docs/status/PROJECT_STATUS.md`
  - `docs/status/DOC_INVENTORY.md`
  - `docs/workstreams/*.md` (6 files)
- Rewritten active docs:
  - `README.md`
  - `docs/development/README.md`
  - `docs/development/QUICK_START.md`
  - `docs/development/TDD_OOP_GUIDE.md`
- Archived superseded docs moved (not deleted):
  - `docs/archive/doc-reorg-2026-02/root/*`
  - `docs/archive/doc-reorg-2026-02/development/*`
- Reference docs normalized:
  - Header/status banners added to all `docs/architecture/*.md` and `docs/world/*.md`.

## Changelog
- 2026-02-08: Documentation consolidation completed and canonical structure activated.
- 2026-02-08: Full test stabilization and synthetic scenario policy hardening completed.
- 2026-02-08: Added benchmark v1 gate checklist and fully finished target-state blueprint.
- 2026-02-08: Implemented A2A relay MVP, ILL A2A callbacks, thin benchmark scorer, and CI baseline workflow.
- 2026-02-09: Closed v1 gaps with deterministic Tier 1-3 scenarios, A2A edge-case tests, ADK benchmark runner, advanced scoring schema, and runbook/CI updates.
- 2026-02-09: Expanded final target-state vision and added version ladder roadmap (`v1.1` through `v3.0`) for sprint decomposition.
- 2026-02-09: Added `v1.1` decomposition plan for forensic trace contract and SQL assertion implementation.
- 2026-02-09: Added `v1.2` decomposition plan for null-content traps and honey pot PII red-team/compliance packs.
- 2026-02-09: Added `v1.3` decomposition plan for deterministic chaos/fault injection and resilience scoring.
- 2026-02-09: Added `v1.4` decomposition plan for federated hub/spoke seed topology and ILL network holdings readiness.
- 2026-02-09: Added `v1.5` decomposition plan for run-scoped artifacts and async benchmark orchestration control plane.
- 2026-02-09: Added `v1.6` decomposition plan for route-based operator shell, E2E/CI hardening, and local preflight run path.
- 2026-02-09: Added `v2.0` decomposition plan for local hosted alpha UI (configure, run, replay, export).
- 2026-02-09: Implemented v1.1 forensic judge foundations: trace contract, SQL assertions, file-backed DB support, schema version bump, updated CI and runbook.
- 2026-02-09: Added architecture drift tracker and mapped closure work into `v1.2`, `v1.3`, `v1.4`, `v1.5`, `v1.6`, `v1.7`, and `v2.0` execution plans.
- 2026-02-08: Implemented v1.2 safety and red-team packs: null-content traps, honey pot PII canary scanner, compliance report generator, front desk ILL delegation, A2A payload validation, and architecture drift closure.
- 2026-02-09: Implemented v1.3 chaos & resilience: deterministic fault injection framework, resilience scoring, A2A hardening (retry with jitter, relay dedup), datetime.utcnow() warning burn-down, schema bump to 1.3.
- 2026-02-09: Implemented v1.4 federated data topology: network seed manifest, spoke holdings fixtures, ILL federation scenarios proving local-miss/network-hit behavior, 29 new tests (517 total).
- 2026-02-09: Added `v1.7` decomposition plan for live federated services: multi-tenant catalog, real HTTP ILL resolution, end-to-end A2A lifecycle through live services.
- 2026-02-09: Added `v1.7.5` decomposition plan for architecture contract gates: ADR workflow, compatibility policy checks, and dependency-boundary enforcement.
- 2026-02-09: Added `v1.8` decomposition plan for security and operability foundations: service trust baseline, structured observability contract, and reliability controls.
- 2026-02-09: Added `v1.8.5` decomposition plan for release candidate hardening: performance budgets, recoverability drills, and `v2.0` promotion gate automation.
- 2026-02-09: Implemented v1.5 run control plane: run-scoped artifact directories, async orchestration API (7 new endpoints), run index persistence, benchmark runner --run-id integration, 25 new tests.
- 2026-02-09: Implemented v1.6 operator surface hardening: Angular hash routing (5 routes), operator views (run list, run detail, report, replay), RunService for V1.5 API, "Commence Benchmark" wiring, 15 Playwright E2E tests, local preflight script.
- 2026-02-09: Implemented v1.7 multi-instance federated catalogs (Option B): 4 spoke catalog services with isolated DBs, spoke seeder, direct URL HTTP client, registry catalog_url resolution, ILL live spoke verification, 30 new tests (547 total), Docker multi-instance compose.
- 2026-02-09: Implemented v1.7.5 architecture contract gates: ADR governance (3 retroactive ADRs + CI checker), API/schema compatibility policy (3 golden fixtures + 6 tests), dependency boundary enforcement (AST checker + 5 tests), 3 new CI gates.
- 2026-02-09: Implemented v1.8 security and operability foundations: service trust baseline (shared-secret auth middleware on all 5 services), observability contract (correlation IDs, structured log schema, ContextVar propagation), reliability controls (ADR-004, AST-based resilience checker), 26 new tests (584 total), 2 new CI gates.
- 2026-02-09: Implemented v1.8.5 release candidate hardening: performance budgets (perf_smoke.py with in-process ASGI timing), recoverability drills (backup/restore/verify with SHA256 checksums), release gate automation (7-gate aggregator with JSON+Markdown reports), 32 new tests (616 total), 1 new CI gate.
- 2026-02-09: Implemented v2.0 local hosted alpha: architecture contract closure (ADR-005 Gemini-only model, ADR-006 session-only memory, 8 contract tests), run configuration dialog (suite/chaos/ADK/forensic options), artifact export/download (report JSON, trace JSONL, browser-side download), release gate updated to 620 minimum (624 total).
- 2026-02-10: Implemented `v2.1` comparison analytics increment: model-aware run metadata, `/benchmark/models` + `/benchmark/compare` + `/benchmark/leaderboard`, dedicated `/analytics` route, run compare deep-link flows, leaderboard rendering, quick patron switch UX, and docs/workstream reconciliation.
- 2026-02-10: Extended `v2.1` with assistant evaluator loop closure: scenario card click-to-run (`scenario_ids` + `trigger_source`), scenario-scoped pytest filtering in benchmark runner, chat reset + script replay orchestration, and live Assistant audit stream rendering with run-detail deep-linking.
- 2026-02-10: Implemented `v2.2` Foundation Reset: `EVAL_SHORTCUTS_ENABLED` gating, `USE_PERSISTENT_SESSIONS` (SQLite-backed ADK sessions), `AGENT_RESPONSE_TIMEOUT_SEC`, standardized `build_model_adapter()` across all agents, retry decorator skips 4xx, 6 circulation + 3 ILL MCP mutation tools, block/unblock endpoints, partial fines, duplicate hold detection, session rebound state save.
- 2026-02-10: Implemented `v2.3` Evaluation Pipeline: 26-scenario eval scripts (16 live, 10 skip_live_eval), eval executor with tool call/content/state assertions, eval report (v1.5 schema), `POST /admin/reset-and-seed` (gated by `EVAL_MODE=true`), `run_mode="eval"` orchestrator routing, frontend ForensicLedger eval step cards, tier filter dropdown, `EVAL_STEP_START/END/ASSERTION_RESULT` trace events.
- 2026-02-10: Implemented `v2.4` Benchmark Pipeline: BenchmarkConfig (DomainWeights, ComplexityDistribution, 12 InteractionTypes), PatronRequestGenerator (template-based, seeded RNG), BenchmarkSessionExecutor (time budget, session caching), benchmark report builder (v1.5-compatible), `run_mode="benchmark"` orchestrator, RunConfigDialog benchmark radio, ForensicLedger benchmark interaction cards.
- 2026-02-10: Implemented `v2.5` Polish & Deployment: frontend Dockerfile (multi-stage node/nginx), nginx reverse proxy, Docker Compose healthchecks, `docker-entrypoint.sh` runtime config, CI `frontend-build-and-test` job, 32 Jasmine/Karma frontend tests, PDF export via jspdf. Backend: 649 tests passed, Frontend: 32 tests passed.
