# Benchmark v1 Definition of Done

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Decision criteria for declaring benchmark v1 complete, plus current gap snapshot
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Ad-hoc completion criteria in chats and notes
- Related Workstream: infrastructure-services, adk-agents, a2a-network, mcp-tooling, evaluation-harness, world-data-governance

## Purpose
Define the minimum complete benchmark (v1), separate from longer-term platform ambitions.

## How To Read This
- `Implemented`: present in code/tests/docs with evidence.
- `Partial`: some capability exists, but not benchmark-grade complete.
- `Missing`: not yet implemented for v1.
- v1 is done only when all rows are `Implemented`.

## v1 Completion Matrix

| Area | v1 Requirement | Current Status | Evidence |
|---|---|---|---|
| Synthetic world/data baseline | Fictional catalog + patron data in repo; no required dependency on real-world titles | Implemented | `data/hanno_memorial_library_catalog.json`, `data/hanno_patrons.json` |
| Synthetic guardrails | Automated scenario guardrail test blocks banned real-world markers | Implemented | `tests/scenarios/test_synthetic_guardrails.py` |
| Core services | Catalog, circulation, ILL, registry service APIs boot and pass service tests | Implemented | `services/*/src/*/main.py`, `uv run pytest services -q` |
| MCP layer | Catalog/circulation/ILL expose MCP tools/resources used by agents | Implemented | `services/*/src/*/mcp_server.py` |
| ADK agents | ADK agents run with tests and basic workflow coverage | Implemented | `agents/src/agents/benchmark_runner.py`, `agents/tests/integration/test_benchmark_runner.py` |
| ILL local lifecycle | Request → fulfillment/deny → return flows stable in service and tests | Implemented | `services/ill/src/ill/routes.py`, `services/ill/tests/` |
| A2A runtime interop | Real cross-library runtime message flow (not just spec docs) for ILL handoff | Implemented | `services/registry/src/registry/a2a_relay.py`, `services/ill/src/ill/routes.py`, `services/ill/tests/integration/test_a2a_happy_path.py`, `services/ill/tests/integration/test_a2a_denial_path.py`, `services/ill/tests/integration/test_a2a_retry_timeout.py` |
| Evaluation scenarios | Deterministic puppet scenarios for T1-T3 with pass/fail assertions | Implemented | `tests/scenarios/test_tier1_catalog.py`, `tests/scenarios/test_tier2_circulation.py`, `tests/scenarios/test_tier3_ill_a2a.py`, `tests/scenarios/test_v1_scenarios_no_skip.py` |
| Scoring output | Repeatable run artifact with task completion, policy compliance, hallucination counters | Implemented | `scripts/benchmark_run.py`, `tests/scenarios/scenario_manifest.json`, `tests/scenarios/test_benchmark_scoring.py` |
| Failure taxonomy | Structured classification of failures (tool misuse, state drift, policy break, hallucination) | Implemented | `scripts/benchmark_taxonomy.py`, `scripts/benchmark_run.py` |
| Reproducibility | Single baseline command path for test and scenario validation | Implemented | `scripts/run_benchmark_v1.sh`, `.github/workflows/ci.yml` |
| Operator runbook | Builder/operator guide with setup + validation + troubleshooting | Implemented | `docs/development/BENCHMARK_RUNBOOK.md`, `docs/development/QUICK_START.md` |

## v1 Exit Criteria
1. A2A runtime interop is implemented and validated with at least one end-to-end multi-library ILL scenario.
2. Scenario suite includes deterministic puppet flows for Tier 1-3 with stable pass/fail assertions.
3. A canonical scoring report is produced for each benchmark run (JSON or Markdown artifact).
4. Failure taxonomy categories are emitted in run output for failed scenarios.
5. `uv run pytest -q` remains green and scenario guardrails remain green.

## v1 Closeout Notes
1. A2A runtime now includes happy path, denial handling, bounded retries, and relay ack idempotency coverage.
2. Tier 1-3 scenarios are deterministic and run in-process without external service/API-key dependency.
3. Scoring artifacts are manifest-driven and include per-scenario metrics + taxonomy output in JSON/Markdown.
4. Reproducible benchmark execution is standardized through `scripts/run_benchmark_v1.sh` and CI.

## Acceptance Commands (v1 Gate)
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q
uv run pytest tests/scenarios -q
uv run pytest agents/tests/integration/test_benchmark_runner.py -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.1 Completion Matrix

| Area | v1.1 Requirement | Status | Evidence |
|---|---|---|---|
| Trace contract | Benchmark run emits structured trace artifacts with schema validation | Implemented | `shared/src/shared/eval/trace_schemas.py`, `shared/src/shared/eval/trace_writer.py`, `tests/scenarios/test_trace_schema.py` |
| Forensic SQL assertions | Benchmark run executes forensic SQL assertions and reports pass/fail by assertion | Implemented | `scripts/forensic_sql.py`, `scripts/forensic_assertions.py`, `tests/scenarios/test_forensic_assertions.py` |
| Report schema bump | JSON and Markdown reports include trace summary and forensic assertion summary | Implemented | `scripts/benchmark_run.py` (schema_version 1.1, trace_summary, forensic_assertions) |
| File-backed DB support | Scenario fixtures persist state for post-run SQL evaluation | Implemented | `tests/scenarios/conftest.py` (_make_engine with BENCHMARK_DB_DIR) |
| CI integration | Trace/assertion tests added to CI pipeline | Implemented | `.github/workflows/ci.yml` |

## v1.1 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_trace_schema.py -q
uv run pytest tests/scenarios/test_forensic_assertions.py -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.2 Completion Matrix

| Area | v1.2 Requirement | Status | Evidence |
|---|---|---|---|
| Null-content trap pack | Deterministic anti-fabrication scenarios with pass/fail scoring | Implemented | `data/null_content_trap_cases.json`, `scripts/safety_evaluator.py`, `tests/scenarios/test_null_content_trap.py` |
| Honey pot PII red-team pack | Canary PII profiles with adversarial leakage detection | Implemented | `data/canary_pii_profiles.json`, `scripts/pii_canary_scanner.py`, `tests/scenarios/test_honey_pot_redteam.py` |
| Compliance report artifacts | JSON and Markdown compliance reports with per-canary/per-attack outcomes | Implemented | `scripts/compliance_report.py`, `tests/scenarios/test_compliance_report_schema.py` |
| Report schema bump | Benchmark report schema 1.2 with safety_summary, null_content_results, pii_leakage_results | Implemented | `scripts/benchmark_run.py` (schema_version 1.2) |
| Safety taxonomy categories | content_fabrication and pii_leakage taxonomy categories | Implemented | `scripts/benchmark_taxonomy.py` |
| Front desk ILL delegation | Front desk agent delegates to ILL escalation sub-agent | Implemented | `agents/src/agents/ill_escalation_agent.py`, `agents/src/agents/tools/ill_tools.py`, `agents/tests/unit/test_front_desk_ill_delegation.py` |
| A2A payload validation | Outbound A2A payloads reject PII-sensitive fields | Implemented | `services/ill/src/ill/a2a_client.py`, `services/ill/tests/unit/test_a2a_payload_validation.py` |
| Architecture doc reconciliation | Service topology and agent hierarchy docs match implementation | Implemented | `docs/architecture/SERVICES.md`, `docs/architecture/AGENTS.md` |

## v1.2 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_null_content_trap.py -q
uv run pytest tests/scenarios/test_honey_pot_redteam.py -q
uv run pytest tests/scenarios/test_compliance_report_schema.py -q
uv run pytest tests/scenarios/test_safety_pack_scoring.py -q
uv run pytest agents/tests -q
uv run pytest services/ill/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.3 Completion Matrix

| Area | v1.3 Requirement | Status | Evidence |
|---|---|---|---|
| Chaos profile schema | Deterministic fault profiles with seeded, call-index-based scheduling | Implemented | `scripts/chaos_profiles.py`, `tests/scenarios/test_chaos_fault_injection.py` |
| Chaos controller | Pure test utility that intercepts service calls and applies faults deterministically | Implemented | `scripts/chaos_controller.py`, `tests/scenarios/test_chaos_fault_injection.py` (13 tests) |
| Resilience scoring | Weighted composite scoring (recovery, budget, degradation, state integrity) | Implemented | `scripts/resilience_evaluator.py`, `tests/scenarios/test_resilience_scoring.py` (7 tests) |
| Chaos integration scenarios | ILL/A2A scenarios under fault injection with state integrity assertions | Implemented | `tests/scenarios/test_tier3_ill_a2a_chaos.py` (4 chaos scenarios) |
| Chaos report artifacts | JSON and Markdown chaos reports with fault matrix and resilience summary | Implemented | `scripts/resilience_evaluator.py`, `tests/scenarios/test_chaos_report_schema.py` (4 tests) |
| A2A retry with jitter | Exponential backoff with jitter for ILL A2A calls | Implemented | `services/ill/src/ill/resilience.py`, `services/ill/tests/integration/test_a2a_retry_timeout.py` |
| A2A relay dedup | Duplicate message detection in registry relay | Implemented | `services/registry/src/registry/a2a_relay.py`, `services/registry/tests/unit/test_a2a_relay_idempotency.py` |
| Warning burn-down | All `datetime.utcnow()` deprecation warnings eliminated | Implemented | 0 matches for `datetime.utcnow` in codebase (7 files updated) |
| Report schema bump | Benchmark report schema 1.3 with chaos_summary, resilience_summary | Implemented | `scripts/benchmark_run.py` (schema_version 1.3) |
| Chaos taxonomy categories | resilience_failure and timeout_exhaustion taxonomy categories | Implemented | `scripts/benchmark_taxonomy.py` |
| Chaos trace events | CHAOS_FAULT_INJECTED, CHAOS_RECOVERY_ATTEMPT, RESILIENCE_SCORE_COMPUTED | Implemented | `shared/src/shared/eval/trace_schemas.py` |
| A2A protocol docs | MVP relay semantics documented with retry contract and dedup behavior | Implemented | `docs/architecture/A2A_PROTOCOL.md` |

## v1.3 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_chaos_fault_injection.py -q
uv run pytest tests/scenarios/test_resilience_scoring.py -q
uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q
uv run pytest tests/scenarios/test_chaos_report_schema.py -q
uv run pytest services/ill/tests -q
uv run pytest services/registry/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.4 Completion Matrix

| Area | v1.4 Requirement | Status | Evidence |
|---|---|---|---|
| Network seed manifest | Canonical batch-to-library ownership map with schema validation | Implemented | `data/network_seed_manifest.json`, `scripts/seed_manifest_validator.py` |
| Manifest validator | Standalone validator checking schema, coverage, counts, duplicates, spoke codes, totals | Implemented | `scripts/seed_manifest_validator.py` (8 checks), `tests/scenarios/test_federated_seed_manifest.py` (12 tests) |
| Spoke holdings fixtures | Session-scoped pytest fixture loading spoke catalogs from manifest sources | Implemented | `tests/scenarios/conftest.py` (spoke_holdings, federated_ill_client) |
| Catalog partitioning | Each library owns a distinct partition of the 635-book corpus with zero overlap | Implemented | `tests/scenarios/test_federated_catalog_partitioning.py` (9 tests) |
| ILL federation scenarios | Local-miss/network-hit ILL behavior validated against federated datasets | Implemented | `tests/scenarios/test_ill_network_holdings_resolution.py` (8 tests) |
| Federated seed orchestrator | Network seed runner with validation + report generation | Implemented | `scripts/seed_network.py`, `scripts/seed_all.py` (--federated flag) |
| Scenario manifest update | Manifest bumped to v1.4 with federated scenario entries | Implemented | `tests/scenarios/scenario_manifest.json` (v1.4, 6 new scenarios) |
| Benchmark ManifestScenario | Extended with requires_federated_seed, expected_source_library, network_lookup_required | Implemented | `scripts/benchmark_run.py` |
| No-skip guard | Federated test files added to V1_SCENARIO_FILES guard list | Implemented | `tests/scenarios/test_v1_scenarios_no_skip.py` |
| Registry partner alignment | tusk-conservatory added to registry fixtures and KNOWN_SOURCE_LIBRARIES | Implemented | `tests/scenarios/conftest.py`, `services/ill/src/ill/routes.py` |
| Genre-specialization alignment | Spoke books' genres match their library's declared specializations | Implemented | `test_ill_network_holdings_resolution.py::test_spoke_specialization_genre_alignment` |
| Network seed report artifact | Federated seed report written to artifacts/network-seed-report.json | Implemented | `scripts/seed_network.py` |

## v1.4 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_federated_seed_manifest.py -q
uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q
uv run python scripts/seed_manifest_validator.py --check-only
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.5 Completion Matrix

| Area | v1.5 Requirement | Status | Evidence |
|---|---|---|---|
| Run metadata models | Pydantic models for RunStatus, RunMetadata, RunIndex, request/response | Implemented | `agents/src/agents/benchmark_api_models.py` |
| Run index persistence | Atomic JSON persistence with file-locking for concurrent safety | Implemented | `agents/src/agents/run_index.py`, `agents/tests/integration/test_run_index_integrity.py` (10 tests) |
| Benchmark orchestrator | Async run lifecycle management with subprocess benchmark execution | Implemented | `agents/src/agents/benchmark_orchestrator.py` |
| API orchestration routes | POST/GET /benchmark/runs, GET /runs/{run_id}, /report, /trace, /artifacts | Implemented | `agents/src/agents/api.py` (7 new routes) |
| Legacy report compatibility | GET /benchmark/report resolves latest successful run then flat fallback | Implemented | `agents/src/agents/api.py`, `agents/tests/integration/test_benchmark_run_lifecycle.py` |
| Run-scoped artifact directories | Artifacts partitioned under artifacts/runs/<run_id>/ with indexed metadata | Implemented | `agents/src/agents/benchmark_orchestrator.py`, `agents/src/agents/run_index.py` |
| Benchmark runner integration | --run-id CLI arg, run_id passthrough to TraceWriter, conditional schema bump | Implemented | `scripts/benchmark_run.py` |
| API lifecycle tests | Integration tests for create/list/get/report/trace/artifacts endpoints | Implemented | `agents/tests/integration/test_benchmark_run_lifecycle.py` (13 tests) |
| Shell wrapper update | v1.5 version labels, run control plane test steps, run index verification | Implemented | `scripts/run_benchmark_v1.sh` |
| TraceWriter run_id passthrough | TraceWriter uses explicit run_id when provided by orchestrator | Implemented | `agents/tests/integration/test_benchmark_runner.py` (2 new tests) |

## v1.5 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
uv run pytest agents/tests -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

## v1.6 Completion Matrix

| Area | v1.6 Requirement | Status | Evidence |
|---|---|---|---|
| Angular routing | Hash-based route navigation with 5 routes + wildcard redirect | Implemented | `frontend/src/app/app.routes.ts`, `frontend/src/app/app.config.ts` |
| Navigation shell | Top nav bar with brand + Chat/Runs links, `<router-outlet>` | Implemented | `frontend/src/app/app.component.ts` |
| Chat page wrapper | Existing 3-panel layout preserved as routed component | Implemented | `frontend/src/app/features/chat-page/chat-page.component.ts` |
| Run list view | Table with status badges, "New Benchmark Run" button, loading/error/empty states | Implemented | `frontend/src/app/features/runs/run-list.component.ts` |
| Run detail view | Metadata display, status polling, report/trace action links, artifact list | Implemented | `frontend/src/app/features/run-detail/run-detail.component.ts` |
| Report view | Summary metrics, progress bar, scenario table, forensic assertions | Implemented | `frontend/src/app/features/reports/report-view.component.ts` |
| Replay view | Trace event timeline with color-coded markers and payload display | Implemented | `frontend/src/app/features/replay/replay-view.component.ts` |
| RunService | API client for all V1.5 run endpoints + polling | Implemented | `frontend/src/app/core/services/run.service.ts` |
| V1.5 TypeScript models | RunMetadata, RunCreateRequest/Response, RunListResponse, TraceEvent | Implemented | `frontend/src/app/shared/models/benchmark.models.ts` |
| Commence Benchmark wiring | ScenarioSidebar button triggers RunService.createRun() and navigates to detail | Implemented | `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts` |
| BenchmarkService run report | loadRunReport(runId) method for run-specific report loading | Implemented | `frontend/src/app/core/services/benchmark.service.ts` |
| E2E: chat smoke | Updated for routed app with hash URLs and nav bar test | Implemented | `frontend/e2e/chat-smoke.spec.ts` (4 tests) |
| E2E: run orchestration | Run list, creation, detail, error, and navigation tests | Implemented | `frontend/e2e/run-orchestration.spec.ts` (6 tests) |
| E2E: report/replay | Report metrics, forensic assertions, trace timeline, error states | Implemented | `frontend/e2e/report-replay.spec.ts` (5 tests) |
| Local preflight script | Prerequisite, port, and service health checker | Implemented | `scripts/run_local_alpha.sh` |

## v1.6 Acceptance Commands
```bash
cd frontend && ng build
cd frontend && npm run e2e
scripts/run_local_alpha.sh
uv run pytest -q
```

## v1.7 Completion Matrix

| Area | v1.7 Requirement | Status | Evidence |
|---|---|---|---|
| Catalog parameterization | Catalog service reads LIBRARY_CODE/LIBRARY_NAME from env vars; /library/info endpoint | Implemented | `services/catalog/src/catalog/routes.py`, `services/catalog/src/catalog/schemas.py` |
| Spoke catalog seeder | CLI seeder provisions individual library catalog DBs from network manifest | Implemented | `scripts/seed_spoke_catalog.py`, `tests/scenarios/test_spoke_catalog_seeding.py` (11 tests) |
| Network provisioner | seed_network.py --mode provision creates per-library SQLite databases | Implemented | `scripts/seed_network.py` |
| Direct URL HTTP client | call_url() and call_remote_catalog() for explicit URL calls to spoke catalogs | Implemented | `shared/src/shared/http_client.py`, `tests/scenarios/test_registry_spoke_resolution.py` (8 tests) |
| Registry catalog_url | catalog_url field on partner library CRUD; registry federation seeder | Implemented | `services/registry/src/registry/schemas.py`, `services/registry/src/registry/routes.py`, `scripts/seed_registry_federation.py` |
| ILL live spoke verification | ILL creation verifies spoke holdings via real HTTP when catalog_url is available | Implemented | `services/ill/src/ill/routes.py` (Step 3b), `services/ill/src/ill/schemas.py` (isbn field) |
| Graceful degradation | ILL proceeds with warning if spoke catalog is unreachable | Implemented | `tests/scenarios/test_live_federation.py::test_graceful_degradation_spoke_unreachable` |
| Live federation fixtures | In-process multi-catalog ASGI test clients with per-spoke seeded databases | Implemented | `tests/scenarios/conftest.py` (live_spoke_catalogs, live_federation_client) |
| Live federation tests | Spoke direct query, ILL with live verification, cross-spoke resolution | Implemented | `tests/scenarios/test_live_federation.py` (11 tests) |
| Docker multi-instance | 4 spoke catalog services in docker-compose with isolated volumes | Implemented | `docker-compose.yml` (catalog-mastodon:8011, catalog-mammoth:8012, catalog-ivory:8013, catalog-tusk:8014) |
| Docker federation seeder | Bash script for health wait, spoke seed, registry seed, smoke test | Implemented | `scripts/seed_docker_federation.sh` |
| Manifest endpoints | network_seed_manifest.json includes endpoints section with port/docker_host per library | Implemented | `data/network_seed_manifest.json` |
| v1.4 backward compat | All v1.4 fixture-based federation tests continue to pass unchanged | Implemented | `tests/scenarios/test_ill_network_holdings_resolution.py` (8 tests still green) |

## v1.7 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_spoke_catalog_seeding.py -q
uv run pytest tests/scenarios/test_registry_spoke_resolution.py -q
uv run pytest tests/scenarios/test_live_federation.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q
```

## v1.7.5 Completion Matrix

| Area | v1.7.5 Requirement | Status | Evidence |
|---|---|---|---|
| ADR scaffolding | Template, index, and naming conventions for architecture decision records | Implemented | `docs/architecture/adr/README.md`, `docs/architecture/adr/ADR_TEMPLATE.md`, `docs/architecture/adr/INDEX.md` |
| Retroactive ADRs | At least 3 retroactive ADRs covering key architecture decisions | Implemented | `docs/architecture/adr/ADR-001-multi-instance-federation.md`, `ADR-002-registry-hosted-a2a-relay.md`, `ADR-003-pytest-manifest-benchmark-engine.md` |
| ADR CI checker | Automated validator for ADR index/file consistency and required sections | Implemented | `scripts/check_adr_links.py` (6 checks, --strict mode) |
| Compatibility policy | Schema versioning rules, additive/breaking change policy, deprecation windows | Implemented | `docs/development/CONTRACT_COMPATIBILITY_POLICY.md` |
| Golden fixtures | Minimal valid fixtures for each schema version under `tests/fixtures/golden/` | Implemented | `tests/fixtures/golden/benchmark-report-v1.1.json`, `run-index-v1.5.json`, `scenario-manifest-v1.4.json` |
| Compatibility tests | Tests verifying golden fixture consumption and breaking change detection | Implemented | `tests/scenarios/test_contract_compatibility.py` (6 tests) |
| Boundary map | Import DAG documenting allowed/forbidden dependencies between layers | Implemented | `docs/development/DEPENDENCY_BOUNDARY_MAP.md` |
| AST boundary checker | Python AST-based import analysis enforcing boundary rules | Implemented | `scripts/check_dependency_boundaries.py` (74 files scanned, 0 violations) |
| Boundary tests | Tests proving checker catches violations, allows relative imports, exempts scripts/tests | Implemented | `tests/scenarios/test_dependency_boundaries.py` (5 tests) |
| CI integration | ADR, compatibility, and boundary gates added to CI pipeline | Implemented | `.github/workflows/ci.yml` (3 new steps) |

## v1.7.5 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run python scripts/check_adr_links.py --strict
uv run pytest tests/scenarios/test_contract_compatibility.py -q
uv run python scripts/check_dependency_boundaries.py --strict
uv run pytest tests/scenarios/test_dependency_boundaries.py -q
```

## v1.8 Completion Matrix

| Area | v1.8 Requirement | Status | Evidence |
|---|---|---|---|
| Service trust primitives | Shared-secret auth module with token injection and middleware validation | Implemented | `shared/src/shared/auth.py` (get_service_token, ServiceAuthMiddleware) |
| Auth middleware deployment | All 5 services enforce X-Service-Token on non-public endpoints | Implemented | `services/*/src/*/main.py`, `agents/src/agents/api.py` |
| HTTP client auth injection | call_service() and call_url() auto-inject auth token in outbound headers | Implemented | `shared/src/shared/http_client.py` |
| Agent tools auth | All httpx.AsyncClient calls in agent tools include auth headers | Implemented | `agents/src/agents/tools/{catalog,circulation,ill}_tools.py` |
| Service trust tests | Rejection/acceptance/public-path tests for all services | Implemented | `tests/scenarios/test_service_trust.py` (10 tests) |
| Observability primitives | StructuredLogEvent schema, ContextVar correlation/run ID propagation | Implemented | `shared/src/shared/observability.py` |
| Correlation middleware | X-Request-ID generation/echo, X-Run-ID propagation on all services | Implemented | `services/*/src/*/main.py`, `agents/src/agents/api.py` |
| Correlation header forwarding | Outbound HTTP calls forward correlation + run ID headers | Implemented | `shared/src/shared/http_client.py` |
| Observability golden fixture | Structured log event golden fixture for schema compatibility | Implemented | `tests/fixtures/golden/structured-log-event-v1.8.json` |
| Observability tests | Schema validation, golden fixture round-trip, correlation header behavior | Implemented | `tests/scenarios/test_observability_contract.py` (8 tests) |
| Reliability policy ADR | ADR-004 codifying timeout/retry/CB defaults | Implemented | `docs/architecture/adr/ADR-004-reliability-policy.md` |
| Resilience policy checker | AST-based checker enforcing @with_retry on httpx tool functions | Implemented | `scripts/check_resilience_policy.py` |
| Reliability tests | Timeout defaults, retry behavior, circuit breaker transitions, health endpoints | Implemented | `tests/scenarios/test_reliability_policy.py` (8 tests) |
| CI integration | Resilience policy check + combined trust/observability/reliability test step | Implemented | `.github/workflows/ci.yml` (2 new steps) |
| Environment configuration | SERVICE_AUTH_TOKEN in .env.example and docker-compose.yml | Implemented | `.env.example`, `docker-compose.yml` |

## v1.8 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_service_trust.py -q
uv run pytest tests/scenarios/test_observability_contract.py -q
uv run pytest tests/scenarios/test_reliability_policy.py -q
uv run python scripts/check_resilience_policy.py --strict
uv run python scripts/check_adr_links.py --strict
```

## v1.8.5 Completion Matrix

| Area | v1.8.5 Requirement | Status | Evidence |
|---|---|---|---|
| Performance budget doc | Documented budget thresholds for local alpha workflows | Implemented | `docs/development/PERFORMANCE_BUDGETS.md` |
| Performance smoke script | In-process ASGI health check timing with JSON report output | Implemented | `scripts/perf_smoke.py` (PerformanceSmokeRunner, 4 service health checks, report generation timing) |
| Performance budget tests | Doc, script, and execution validation tests | Implemented | `tests/scenarios/test_performance_budgets.py` (8 tests) |
| Recovery runbook | Backup/restore/verify procedures for run artifacts | Implemented | `docs/development/RECOVERY_AND_ROLLBACK_RUNBOOK.md` |
| Recovery drill script | Automated backup/restore/verify/drill cycle with SHA256 checksums | Implemented | `scripts/recovery_drill.py` (RecoveryDrillRunner, 4 subcommands) |
| Recovery drill tests | Backup, restore, and verify operation validation | Implemented | `tests/scenarios/test_recovery_drill.py` (10 tests) |
| Release gate script | Unified v2.0 RC promotion gate aggregating 7 sub-gates | Implemented | `scripts/release_gate_v2_0_rc.py` (ReleaseGateRunner, JSON + Markdown reports) |
| Release gate report schema | Schema validation and status logic tests | Implemented | `tests/scenarios/test_release_gate_report_schema.py` (14 tests) |
| CI integration | Release gate step added to CI pipeline | Implemented | `.github/workflows/ci.yml` (1 new step) |
| Promotion readiness | Overall status (promotable/blocked/partial) computed from gate results | Implemented | `scripts/release_gate_v2_0_rc.py` (compute_overall_status) |

## v1.8.5 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_performance_budgets.py -q
uv run pytest tests/scenarios/test_recovery_drill.py -q
uv run pytest tests/scenarios/test_release_gate_report_schema.py -q
uv run python scripts/perf_smoke.py --strict
uv run python scripts/release_gate_v2_0_rc.py --strict --skip-frontend
```

## v2.0 Completion Matrix

| Area | v2.0 Requirement | Status | Evidence |
|---|---|---|---|
| Model provider ADR | Explicit decision record codifying Gemini-only model contract | Implemented | `docs/architecture/adr/ADR-005-single-provider-model-contract.md` |
| Memory contract ADR | Explicit decision record codifying session-only memory | Implemented | `docs/architecture/adr/ADR-006-session-only-memory-contract.md` |
| ADR index update | INDEX.md includes ADR-005 and ADR-006 | Implemented | `docs/architecture/adr/INDEX.md` (6 ADRs) |
| Model/memory contract tests | Tests preventing drift toward multi-provider or persistent memory | Implemented | `tests/scenarios/test_model_memory_contract.py` (8 tests) |
| Run configuration dialog | Modal dialog exposing suite, chaos profile, ADK toggle, forensic toggle | Implemented | `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts` |
| Sidebar config integration | "Commence Benchmark" opens config dialog instead of hardcoded params | Implemented | `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts` |
| Run list config integration | "New Benchmark Run" opens config dialog instead of hardcoded params | Implemented | `frontend/src/app/features/runs/run-list.component.ts` |
| Download utility | Browser-side Blob download for JSON and text files | Implemented | `frontend/src/app/shared/utils/download.ts` |
| Report export | Export JSON button on benchmark report view | Implemented | `frontend/src/app/features/reports/report-view.component.ts` |
| Trace export | Export JSONL button on trace replay view | Implemented | `frontend/src/app/features/replay/replay-view.component.ts` |
| Run detail downloads | Download Report and Download Trace buttons on run detail view | Implemented | `frontend/src/app/features/run-detail/run-detail.component.ts` |
| Release gate update | Minimum test count raised to 620 | Implemented | `scripts/release_gate_v2_0_rc.py` |

## v2.0 Acceptance Commands
```bash
uv sync --all-packages
uv run pytest -q
uv run pytest tests/scenarios/test_model_memory_contract.py -q
uv run python scripts/check_adr_links.py --strict
cd frontend && npx ng build
uv run python scripts/release_gate_v2_0_rc.py --strict --skip-frontend
```

## Assumptions
- v1 does not require a full production UI.
- v1 requires at least one real A2A runtime path, not just planned docs.
- v1 prioritizes benchmark reliability over feature breadth.
