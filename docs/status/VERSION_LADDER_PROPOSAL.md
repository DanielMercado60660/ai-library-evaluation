# Version Ladder Proposal

## Doc Header
- Doc Status: Planned
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Version-by-version roadmap from v1 baseline to fully finished platform
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Ad-hoc roadmap notes in chats
- Related Workstream: infrastructure-services, adk-agents, a2a-network, mcp-tooling, evaluation-harness, world-data-governance

## Purpose
Turn the long-range platform vision into a release ladder (`v1.1`, `v1.2`, `v2.0`, etc.) with sprint-sized execution units, explicit acceptance tests, and clear non-goals per version.

## Planning Assumptions
1. `v1.0` baseline is complete and stable.
2. Every version must be productionizable at its own scope before moving up the ladder.
3. Deterministic correctness remains the top priority over feature breadth.
4. Each version should fit in 1-3 sprints.

## Architecture Drift Alignment
The architecture documents are intentionally treated as a design baseline, and closures are versioned so drift is reduced without freezing delivery.

| Drift Theme | Current Gap | Closure Version |
|---|---|---|
| Service topology mismatch | Docs still describe split registry + broker on `7001/7002` while runtime is registry-hosted relay on `8004` | `v1.2` |
| Front desk orchestration gap | Front desk delegations are catalog/circulation-first; ILL escalation is not yet first-class in orchestration flow | `v1.2` |
| A2A protocol/runtime mismatch | Long-form protocol describes broader semantics than current HTTP relay MVP | `v1.3` |
| Warning noise in regression output | High warning volume obscures true failures | `v1.3` |
| Federated catalog topology gap | Only single-library seeding exists; hub/spoke catalog state and partner holdings are not versioned for deterministic ILL evaluation | `v1.4` |
| Run identity/orchestration gap | Runtime exposes only latest benchmark artifact and lacks run-scoped API lifecycle | `v1.5` |
| Operator routing + CI flow gap | Frontend remains single-shell and CI lacks operator-route regression coverage | `v1.6` |
| Live federation gap | Spoke holdings resolved via monkeypatched fixtures rather than real service calls | `v1.7` |
| Architecture governance gap | ADR discipline, API/schema version policy, and dependency-boundary enforcement are not formalized as release gates | `v1.7.5` |
| Security and operability gap | Service trust, structured telemetry, and runtime SLO/error-budget controls are not yet enforced | `v1.8` |
| Release hardening gap | Performance budgets, rollback drills, and release-candidate checklists are incomplete for alpha promotion | `v1.8.5` |
| Provider abstraction gap | Cross-provider model adapter contract remains planned | `v2.0` -> `v2.1` |
| Memory architecture gap | Dedicated memory service not implemented; session memory is primary | `v2.0` (contract) |

Reference: `docs/status/ARCHITECTURE_DRIFT_REPORT.md`

## Current Baseline (`v1.0`)
### Delivered
- Deterministic Tier 1-3 benchmark scenarios.
- ADK + MCP core flows and A2A runtime MVP.
- Manifest-driven scorer and taxonomy.
- CI baseline and runbook.

### Evidence
- `uv run pytest -q` (green baseline)
- `scripts/benchmark_run.py`
- `services/registry/src/registry/a2a_relay.py`
- `services/ill/src/ill/a2a_client.py`

## Version Roadmap at a Glance

| Version | Theme | Primary Outcome |
|---|---|---|
| `v1.1` | Forensic Judge foundations | Deterministic trace contract + SQL integrity assertions in benchmark output |
| `v1.2` | Safety and red-team packs | Null-content hallucination trap + honey pot PII tests with compliance report |
| `v1.3` | Chaos and resilience | Fault injection scenarios and resilience scoring under degraded infrastructure |
| `v1.4` | Federated data topology | Hub/spoke seed pipeline and deterministic network holdings for ILL scenarios |
| `v1.5` | Run control plane | Run-scoped artifacts and async benchmark orchestration API |
| `v1.6` | Operator hardening | Route-based operator shell, E2E/CI hardening, and local alpha preflight path |
| `v1.7` | Live federated services | Multi-tenant catalog, real HTTP ILL resolution, end-to-end A2A lifecycle |
| `v1.7.5` | Architecture contract gates | ADR workflow, API/schema compatibility policy, and enforceable module boundaries |
| `v1.8` | Security and operability foundations | Service trust baseline, structured observability, and reliability controls |
| `v1.8.5` | Release candidate hardening | Performance budgets, backup/restore drills, and promotion checklist automation |
| `v2.0` | Hosted platform alpha | End-to-end UI workflow for configure, run, replay, and export |
| `v2.1` | Cross-model comparison | Gemini-variant run comparison APIs + analytics route + deterministic leaderboard + assistant scenario click-to-run live audit (in progress) |
| `v2.2` | RL data productization | Stable trajectory/preference export pipeline with taxonomy labels |
| `v3.0` | Ecosystem maturity | Open benchmark distribution model + domain-transfer toolkit |

---

## `v1.1` Forensic Judge Foundations

### Goal
Move from proxy scoring to deterministic forensic assertions tied to trace and DB state.

### Sprint decomposition
1. Sprint `v1.1-a`: Trace contract
- Deliverable: canonical trace schema and instrumentation in agents/services/scorer.
- Tests:
  - schema validation tests for emitted traces
  - replay determinism checks for fixed seed scenarios
2. Sprint `v1.1-b`: SQL assertion core
- Deliverable: inventory conservation and financial integrity checks in scorer output.
- Tests:
  - synthetic mutation tests proving assertion catches drift
  - golden-file benchmark artifact tests

### Exit criteria
1. Benchmark artifact includes deterministic SQL assertion section.
2. Failed assertions are linked to exact offending trace/database evidence.
3. Regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Full adversarial suite.
- Hosted UI features.

---

## `v1.2` Safety and Red-Team Packs

### Goal
Add deterministic safety evaluation packs with binary pass/fail outcomes, while closing the highest-impact architecture drift items that block reliable local evaluation workflows.

### Sprint decomposition
1. Sprint `v1.2-a`: Null-content trap
- Deliverable: scenario pack that requests unavailable content (quotes/passages/themes).
- Tests:
  - fail on fabricated content not present in retrieved context
  - pass on explicit "not available in system" behavior
2. Sprint `v1.2-b`: Honey pot compliance pack
- Deliverable: canary PII dataset + attack scripts + compliance report export.
- Tests:
  - direct extraction attacks
  - authority-bias attacks
  - incremental reconstruction attacks

### Exit criteria
1. Null-content and honey pot packs run in CI.
2. Compliance report export includes explicit pass/fail per canary.
3. Safety failures map into taxonomy output consistently.
4. Architecture docs are updated to reflect live service topology and front desk orchestration reality.

### Non-goals
- Cross-model orchestration.
- Chaos controller runtime.

---

## `v1.3` Chaos and Resilience

### Goal
Test recovery and correctness under infrastructure faults and noisy interactions, and harden A2A/runtime quality to reduce productionization risk.

### Sprint decomposition
1. Sprint `v1.3-a`: Fault injection middleware
- Deliverable: injectable timeout, 500, malformed JSON, and partial outage behaviors.
- Tests:
  - deterministic fault replay tests
  - idempotent retry behavior tests
2. Sprint `v1.3-b`: Resilience scenarios and scoring
- Deliverable: chaos scenario pack + resilience sub-score in benchmark artifact.
- Tests:
  - graceful degradation assertions
  - no-silent-failure assertions
  - state consistency checks after faulted runs

### Exit criteria
1. Chaos scenarios are deterministic and repeatable.
2. Resilience metrics appear in benchmark reports.
3. A2A flows recover cleanly or fail explicitly under induced faults.
4. Deprecation/ORM warning volume is materially reduced from current baseline.

### Non-goals
- Hosted product UX.

---

## `v1.4` Federated Data Topology

### Goal
Establish a deterministic hub-and-spoke data foundation for ILL evaluation by introducing per-library catalog seeds, a reproducible network seeding workflow, and explicit partner holdings contracts.

### Sprint decomposition
1. Sprint `v1.4-a`: Seed topology and dataset contract
- Deliverable: network seed manifest that maps hub + spokes to batch datasets with stable IDs.
- Tests:
  - manifest schema validation
  - unique-ID and collision checks across library partitions
2. Sprint `v1.4-b`: Multi-library seeding and deterministic snapshots
- Deliverable: seed runner that provisions catalog/registry/ILL datasets for hub + spokes.
- Tests:
  - reproducible seeded counts across repeated runs
  - smoke ILL scenarios proving network holdings lookup works
3. Sprint `v1.4-c`: Federation integration and docs closeout
- Deliverable: runbook and scenario updates consuming federated seeded datasets.
- Tests:
  - benchmark smoke pack using federated seed mode
  - docs + status evidence updates

### Exit criteria
1. Hub + spoke catalogs can be seeded deterministically with one command path.
2. Registry entries and partner holdings references align with seeded catalogs.
3. ILL scenarios can resolve books that are absent locally but present in at least one spoke.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Multi-tenant production data governance platform.
- Public-hosted federation control plane.

---

## `v1.5` Run Control Plane

### Goal
Introduce a deterministic run lifecycle API and run-scoped artifact model so benchmark execution is addressable by `run_id` rather than only "latest artifact" semantics.

### Sprint decomposition
1. Sprint `v1.5-a`: Run identity and artifact partitioning
- Deliverable: `artifacts/runs/<run_id>/` output contract with index metadata.
- Tests:
  - run-id uniqueness and deterministic artifact-path checks
  - backward compatibility for legacy `artifacts/benchmark-report.json`
2. Sprint `v1.5-b`: Async orchestration API
- Deliverable: `POST/GET /benchmark/runs*` endpoints with status transitions.
- Tests:
  - lifecycle transitions (`queued -> running -> passed|failed`)
  - invalid run-id and missing-artifact path tests
3. Sprint `v1.5-c`: Runner/API integration closeout
- Deliverable: benchmark runner and wrapper scripts updated to emit run-indexed outputs.
- Tests:
  - smoke suite via orchestration API
  - regression suite remains deterministic

### Exit criteria
1. Benchmarks can be launched and queried by `run_id`.
2. Artifact metadata is indexed and reproducible across reruns.
3. Existing CLI flows remain backward-compatible.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Full operator UX for route-driven benchmark control.
- Model-comparison orchestration.

---

## `v1.6` Operator Surface Hardening

### Goal
Bridge backend orchestration into a stable operator-facing shell by adding route-based UI surfaces, run/report/replay data wiring, and CI smoke coverage before full hosted-alpha completion.

### Sprint decomposition
1. Sprint `v1.6-a`: Route-based operator shell
- Deliverable: frontend routes for chat, runs, run detail, reports, and replay.
- Tests:
  - route navigation and missing-run handling
  - read-only rendering from run-indexed backend APIs
2. Sprint `v1.6-b`: E2E + CI hardening
- Deliverable: Playwright suites and CI jobs for operator route smoke coverage.
- Tests:
  - mocked backend E2E
  - live-backend smoke in reproducible local path
3. Sprint `v1.6-c`: Local alpha preflight path
- Deliverable: one-command local preflight/start script and updated troubleshooting docs.
- Tests:
  - dependency/port preflight checks
  - reproducible run/report/replay shell startup

### Exit criteria
1. Operator shell routes are stable and data-backed.
2. Frontend smoke/E2E checks run in CI with failure evidence.
3. Local launch/preflight path is documented and reproducible.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Final hosted-alpha feature completeness claims.
- Cross-provider model adapter closure.
- Live federated service wiring (deferred to `v1.7`).

---

## `v1.7` Live Federated Services

### Goal
Upgrade v1.4's fixture-based federation into live service federation where spoke holdings are resolved through real HTTP calls between running services, closing the gap between test fixtures and production-realistic ILL workflows.

### Sprint decomposition
1. Sprint `v1.7-a`: Catalog multi-tenancy
- Deliverable: `library_code` field on BookModel; spoke holdings seeded into catalog DB.
- Tests:
  - library_code filtering and default behavior
  - backward compatibility for existing single-library queries
2. Sprint `v1.7-b`: ILL live resolution
- Deliverable: ILL routes resolve spoke books via live catalog HTTP calls (no monkeypatching).
- Tests:
  - live ILL request creation for spoke books
  - live holdings query resolution for spoke ISBNs
3. Sprint `v1.7-c`: End-to-end federation lifecycle
- Deliverable: full ILL lifecycle through live services with A2A message verification.
- Tests:
  - local-miss -> spoke-hit -> ILL request -> A2A notification round-trip
  - v1.4 fixture-based tests continue to pass unchanged

### Exit criteria
1. Spoke catalogs are seeded into real service databases.
2. ILL resolution uses live HTTP calls rather than monkeypatched fixtures.
3. A2A messages flow through live registry relay for cross-library requests.
4. v1.4 fixture-based tests remain green as fast deterministic baseline.
5. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Multi-instance service deployment (separate catalog per library).
- Production multi-tenant isolation or access control.

---

## `v1.7.5` Architecture Contract Gates

### Goal
Introduce explicit architecture and contract governance so release scope is enforced by tests and policy rather than informal conventions.

### Sprint decomposition
1. Sprint `v1.7.5-a`: ADR and decision-governance baseline
- Deliverable: ADR template + required ADR index for architecture-significant changes.
- Tests:
  - CI check that new architecture-impacting PRs reference ADR IDs
  - lint for stale ADR links in status/architecture docs
2. Sprint `v1.7.5-b`: API/schema compatibility policy
- Deliverable: semver-like compatibility rules for run artifacts and service API payloads.
- Tests:
  - contract tests for backward compatibility of `benchmark-report` and run-index schemas
  - golden fixtures for API response compatibility across minor versions
3. Sprint `v1.7.5-c`: Dependency-boundary enforcement
- Deliverable: module boundary map and static checks preventing forbidden cross-layer imports.
- Tests:
  - import-boundary tests for agents/services/shared layers
  - CI gate that fails on boundary violations

### Exit criteria
1. Architecture-significant changes require ADR linkage.
2. Artifact and API compatibility checks run in CI.
3. Boundary-rule violations fail fast in local and CI workflows.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Public governance website or external RFC tooling.
- Full organizational process automation beyond repo-level policy checks.

---

## `v1.8` Security and Operability Foundations

### Goal
Raise production-readiness of the local alpha stack by enforcing minimum service trust, telemetry consistency, and resilience controls.

### Sprint decomposition
1. Sprint `v1.8-a`: Service trust baseline
- Deliverable: signed service identity and shared-secret/token rotation policy for inter-service requests.
- Tests:
  - unauthorized inter-service request denial tests
  - token expiry/rotation behavior tests
2. Sprint `v1.8-b`: Structured observability contract
- Deliverable: standard log/event envelope with `run_id`, `request_id`, `library_code`, and status dimensions.
- Tests:
  - schema validation for logs/events across agents + services
  - trace correlation tests from UI action to backend artifact write
3. Sprint `v1.8-c`: Reliability controls and SLO guardrails
- Deliverable: timeout/circuit-breaker policy and baseline SLO targets for key APIs.
- Tests:
  - controlled degradation tests for service timeout and retry exhaustion
  - SLO conformance checks on smoke benchmark workloads

### Exit criteria
1. Inter-service calls enforce trust/auth rules in benchmark-critical paths.
2. Logs and trace events are correlated by run/request identifiers.
3. Reliability controls are documented and validated with deterministic tests.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- Full enterprise IAM integration.
- Production cloud monitoring stack rollout.

---

## `v1.8.5` Release Candidate Hardening

### Goal
Create an explicit alpha-promotion gate that validates performance, recoverability, and release rollback safety before `v2.0`.

### Sprint decomposition
1. Sprint `v1.8.5-a`: Performance and capacity budgets
- Deliverable: benchmark runtime and route-latency budgets for local alpha profile.
- Tests:
  - repeatable performance smoke suite with budget thresholds
  - regression alerts when p95 timings exceed declared limits
2. Sprint `v1.8.5-b`: Recoverability and rollback drills
- Deliverable: backup/restore and rollback runbook for artifacts, run index, and seeded datasets.
- Tests:
  - restore-from-backup verification on seeded environment
  - rollback drill proving prior stable tag can boot and run smoke suite
3. Sprint `v1.8.5-c`: Release candidate gate automation
- Deliverable: `v2.0-rc` checklist command that aggregates contract, security, reliability, and E2E gates.
- Tests:
  - CI job proving checklist fails on any gate breach
  - dry-run release report artifact generation

### Exit criteria
1. Performance budgets are codified and enforced in CI.
2. Backup/restore and rollback drills are reproducible and documented.
3. A single release-gate command determines `v2.0` readiness.
4. Global regression command remains green:
   - `uv run pytest -q`

### Non-goals
- High-scale load testing for cloud production traffic.
- Multi-region disaster recovery.

---

## `v2.0` Hosted Platform Alpha

### Goal
Deliver a usable platform surface for operators to configure and run benchmarks without code edits, building on the contract/security/release gates closed in `v1.7.5`-`v1.8.5`.

### Sprint decomposition
1. Sprint `v2.0-a`: Run orchestration UI
- Deliverable: scenario picker, model config, run launch controls.
- Tests:
  - frontend E2E for launch flow
  - backend API contract tests for run orchestration
2. Sprint `v2.0-b`: Session replay and report center
- Deliverable: trace timeline + report rendering/export UI.
- Tests:
  - replay fidelity tests against trace artifacts
  - export tests for JSON/Markdown/PDF stubs
3. Sprint `v2.0-c`: Scenario configuration agent
- Deliverable: natural-language scenario setup agent grounded in world docs.
- Tests:
  - generated scenario validation against schema
  - deterministic fixture generation for repeated prompts

### Exit criteria
1. Operator can configure, run, replay, and export from UI.
2. Frontend smoke and integration E2E suites are stable.
3. UI-driven run artifacts match CLI-run artifact schema.
4. Adapter and memory contracts from pre-v2 gates are integrated and verified in UI-driven flows.
5. Release candidate gate from `v1.8.5` passes with no blocking failures.

### Non-goals
- Public leaderboard launch.

---

## `v2.1` Cross-Model Comparison, Leaderboard, and Assistant Live Audit

### Goal
Enable normalized model-vs-model benchmarking on identical scenario sets.

### Status (2026-02-10)
Complete. All planned v2.1 deliverables shipped:
1. Model-aware run metadata (`model_name`, `model_family`) in run create/index contracts.
2. New endpoints:
   - `GET /benchmark/models`
   - `POST /benchmark/compare`
   - `GET /benchmark/leaderboard`
3. Dedicated frontend analytics route (`/#/analytics`) with run compare workbench, delta tables, and leaderboard.
4. Compare deep-link flows from run list and run detail.
5. Quick patron switch in top bar for evaluator persona toggling.
6. Assistant scenario click-to-run contract:
   - additive run fields (`scenario_ids`, `trigger_source`)
   - scenario-scoped runner filtering via `--scenario-id`
   - live assistant forensic stream wired from run trace polling.
7. Identity-bound assistant contract:
   - `/chat` accepts active patron context and returns bound patron/session rotation metadata
   - active-profile self-tools for circulation and ILL account flows
   - prompt-driven patron switch behavior (`fresh` vs `keep`) for chat contexts
8. v2.2-prep seams landed in `v2.1.x`:
   - ADR-007/008/009 accepted
   - model adapter factory seam introduced (Gemini implementation only)

### Sprint decomposition
1. Sprint `v2.1-a`: Model-aware run metadata, analytics restore, and assistant scenario execution loop
- Deliverable: additive run contract + analytics page + compare/leaderboard API + assistant click-to-run/live audit stream.
- Tests:
  - run-index compatibility tests
  - deterministic compare/leaderboard API tests
  - frontend analytics E2E tests
  - assistant scenario click-to-run E2E tests
2. Sprint `v2.1-b`: Identity-bound assistant and architecture prep seams
- Deliverable: active-profile chat binding + session rotation + account self-tools + ADR closure + adapter seam scaffolding.
- Tests:
  - chat identity binding integration tests
  - active-patron tool unit tests
  - chat/profile E2E switch-behavior tests
3. Sprint `v2.1-c`: Multi-provider execution abstraction (deferred)
- Deliverable: provider adapter expansion and batch execution matrix beyond Gemini.
- Tests:
  - adapter conformance tests
  - deterministic cross-provider run matrix tests

### Exit criteria
1. Same scenario manifest runs across configured model variants in one command.
2. Comparison report exposes score deltas and taxonomy differences.
3. Leaderboard payloads are generated and validated.
4. Assistant account flows resolve from active profile context without patron-ID prompts in normal chat UX.

### Non-goals
- Full commercial billing/entitlements.

---

## `v2.2` Foundation Reset — Complete (2026-02-10)

### Goal
Harden agent infrastructure for reliable evaluation: gate deterministic shortcuts, standardize model injection, add persistent sessions, expand MCP tools.

### Delivered
- `EVAL_SHORTCUTS_ENABLED` env var (default `false`) gates all deterministic shortcut/fallback paths in agents
- `USE_PERSISTENT_SESSIONS` env var (default `false`) enables SQLite-backed sessions via ADK DatabaseSessionService
- `AGENT_RESPONSE_TIMEOUT_SEC` env var (default `60`) for configurable timeout
- All agents use `build_model_adapter().to_adk_model_ref()` (standardized model injection)
- Refusal markers + patron ID prompt markers consolidated into `agents/config.py`
- Retry decorator skips 4xx client errors (only retries transient/5xx)
- 6 circulation mutation MCP tools, 3 ILL mutation MCP tools
- Circulation: block/unblock endpoints, partial fines, duplicate hold detection
- ILL: book title fetch from spoke catalogs, dynamic earliest_return_date
- Session rebound saves state before rotation (prevents cross-patron data leak)

---

## `v2.3` Evaluation Pipeline — Complete (2026-02-10)

### Goal
Scripted scenario replay with deterministic assertion checking and structured eval reporting.

### Delivered
- Eval scripts manifest: 26 scenarios (16 live, 10 skip_live_eval)
- Eval executor: replays scripts via POST /chat, asserts tool calls, content, and state
- Eval report: maps results to v1.5 report schema with `eval_details`
- Admin seed endpoint: `POST /admin/reset-and-seed` on all 4 services (gated by `EVAL_MODE=true`)
- Orchestrator: `run_mode="eval"` routes to eval execution pipeline
- Frontend: ForensicLedger shows hierarchical eval step cards with pass/fail, tool chips, assertions
- Sidebar: Tier filter dropdown (All/T1/T2/T3), run mode toggle (Eval/Pytest) in config dialog
- Trace events: `EVAL_STEP_START`, `EVAL_STEP_END`, `EVAL_ASSERTION_RESULT`

---

## `v2.4` Benchmark Pipeline (Open-Ended) — Complete (2026-02-10)

### Goal
Template-based open-ended benchmark generation with deterministic seeding, session-cached execution, and structured reporting.

### Delivered
- BenchmarkConfig: DomainWeights, ComplexityDistribution, 12 InteractionTypes, TOOL_HINTS
- PatronRequestGenerator: template-based, deterministic (seeded RNG), loads from seed data
- BenchmarkSessionExecutor: POSTs to /chat, time budget, session caching for sequences
- Report builder: v1.5-compatible summary + benchmark_details extension
- Orchestrator: `run_mode="benchmark"` routes to benchmark execution pipeline
- Frontend RunConfigDialog: third radio "Benchmark (Open-Ended)" with interaction count, time budget, domain/complexity weights, seed
- Frontend ForensicLedger: benchmark interaction cards (compact, expandable, validation chips), footer metrics

---

## `v2.5` Polish & Deployment — Complete (2026-02-10)

### Goal
Production-ready Docker packaging, CI pipeline, frontend testing, and PDF export.

### Delivered
- Frontend Dockerfile: multi-stage (node:20-alpine -> nginx:1.27-alpine)
- nginx.conf: SPA routing + reverse proxy to agents backend (/chat, /benchmark, /health, /admin)
- Runtime config: `docker-entrypoint.sh` generates `env.js` from env vars
- Docker Compose: agents healthcheck, frontend service on port 4200, depends_on agents healthy
- CI: `.github/workflows/ci.yml` with parallel `frontend-build-and-test` job
- Frontend tests: 32 Jasmine/Karma specs (ChatService 9, BenchmarkService 13, RunService 10)
- PDF export: `jspdf` + `jspdf-autotable`, ForensicLedger "Print Report" button
- Test counts: Backend 649 passed, Frontend 32 passed

---

## `v3.0` Ecosystem Maturity (Future)

### Goal
Establish the benchmark as a sustainable open ecosystem with reusable methodology.

### Sprint decomposition
1. Sprint `v3.0-a`: Open-source packaging hardening
- Deliverable: under-30-minute local install path and sample report pack.
- Tests:
  - fresh-clone install tests
  - docs command verification tests
2. Sprint `v3.0-b`: Domain-transfer toolkit
- Deliverable: world-bible-to-corpus generation framework for new domains.
- Tests:
  - reference domain generation tests
  - schema integrity tests
3. Sprint `v3.0-c`: Community extension model
- Deliverable: scenario pack plugin contract and contribution QA pipeline.
- Tests:
  - plugin compatibility tests
  - scenario quality gate tests

### Exit criteria
1. External users can stand up and extend the benchmark without core-team handholding.
2. Domain-transfer workflow is documented and validated by at least one non-library reference pack.

### Non-goals
- Replacing domain experts in safety-sensitive environments.

## Cross-Version Guardrails
1. Keep `uv run pytest -q` as global stability gate.
2. Keep synthetic-only policy enforced in active scenario suites.
3. Require artifact schema versioning for each major/minor version increment.
4. Require changelog entries in:
   - `docs/status/PROJECT_STATUS.md`
   - `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md` (until replaced by v2 DoD doc)

## Next Planning Output
Use this ladder to maintain one decomposition doc per upcoming version:
- `docs/status/V1_1_EXECUTION_PLAN.md` (created)
- `docs/status/V1_2_EXECUTION_PLAN.md` (created)
- `docs/status/V1_3_EXECUTION_PLAN.md` (created)
- `docs/status/V1_4_EXECUTION_PLAN.md` (created)
- `docs/status/V1_5_EXECUTION_PLAN.md` (created)
- `docs/status/V1_6_EXECUTION_PLAN.md` (created)
- `docs/status/V1_7_EXECUTION_PLAN.md` (created)
- `docs/status/V1_7_5_EXECUTION_PLAN.md` (created)
- `docs/status/V1_8_EXECUTION_PLAN.md` (created)
- `docs/status/V1_8_5_EXECUTION_PLAN.md` (created)
- `docs/status/V2_0_EXECUTION_PLAN.md` (created)
- `docs/status/V2_1_EXECUTION_PLAN.md` (created)
- `docs/status/V2_2_EXECUTION_PLAN.md` (next)
