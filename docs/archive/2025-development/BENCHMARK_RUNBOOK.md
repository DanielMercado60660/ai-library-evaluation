# Benchmark Runbook

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Reproducible v1.1/v1.2/v1.3/v1.4/v1.5/v1.6/v1.7 benchmark execution, artifact interpretation, and troubleshooting
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: v1 runbook (prior to trace contract and forensic assertions)
- Related Workstream: evaluation-harness

## Purpose
Provide a single reproducible path for running the v1.1 benchmark and interpreting results.

## v1.1 One-Command Path
```bash
cd ai-library-evaluation
scripts/run_benchmark_v1.sh
```

Optional suite override:
```bash
scripts/run_benchmark_v1.sh smoke
scripts/run_benchmark_v1.sh scenarios
```

## What the Runner Executes
1. `uv sync --all-packages`
2. `uv run pytest -q`
3. `uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q`
4. `uv run pytest --no-cov tests/scenarios/test_trace_schema.py -q`
5. `uv run pytest --no-cov tests/scenarios/test_forensic_assertions.py -q`
6. `uv run python scripts/benchmark_run.py --suite <suite> --include-adk`
7. Verification of forensic artifact presence

## V1.2 Safety Pack Commands
```bash
uv run pytest tests/scenarios/test_null_content_trap.py -q
uv run pytest tests/scenarios/test_honey_pot_redteam.py -q
uv run pytest tests/scenarios/test_compliance_report_schema.py -q
```

## V1.3 Chaos & Resilience Commands
```bash
# Chaos controller unit tests
uv run pytest tests/scenarios/test_chaos_fault_injection.py -q

# Resilience scoring tests
uv run pytest tests/scenarios/test_resilience_scoring.py -q

# Chaos integration scenarios (ILL under fault injection)
uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q

# Chaos report schema validation
uv run pytest tests/scenarios/test_chaos_report_schema.py -q

# A2A hardening (retry with jitter + relay dedup)
uv run pytest services/ill/tests -q
uv run pytest services/registry/tests -q

# Full benchmark with chaos profile
CHAOS_PROFILE=a2a_timeout_on_send uv run python scripts/benchmark_run.py --suite scenarios --include-adk --chaos-profile a2a_timeout_on_send
```

## V1.4 Federated Data Topology Commands
```bash
# Manifest integrity tests
uv run pytest tests/scenarios/test_federated_seed_manifest.py -q

# Catalog partitioning tests
uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q

# ILL federation scenarios
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q

# Standalone manifest validator
uv run python scripts/seed_manifest_validator.py --check-only

# Federated seed orchestrator (validate + report)
uv run python scripts/seed_network.py

# Seed all with federated mode
uv run python scripts/seed_all.py --federated --yes
```

## V1.5 Run Control Plane Commands
```bash
# Create a benchmark run via API
curl -X POST http://127.0.0.1:8000/benchmark/runs \
  -H 'Content-Type: application/json' \
  -d '{"suite": "scenarios", "include_adk": true}'

# Check run status
curl -s http://127.0.0.1:8000/benchmark/runs/{run_id} | jq .status

# List all runs
curl -s http://127.0.0.1:8000/benchmark/runs | jq

# Get run-specific report
curl -s http://127.0.0.1:8000/benchmark/runs/{run_id}/report | jq .summary

# Get run trace events
curl -s http://127.0.0.1:8000/benchmark/runs/{run_id}/trace | jq length

# List run artifacts
curl -s http://127.0.0.1:8000/benchmark/runs/{run_id}/artifacts | jq .artifacts

# Run index integrity tests
uv run pytest agents/tests/integration/test_run_index_integrity.py -q

# Run lifecycle tests
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
```

### V1.5 Artifact Layout
```
artifacts/
├── runs/
│   ├── index.json                    # Run index with all run metadata
│   ├── run-<id>/
│   │   ├── benchmark-report.json
│   │   ├── benchmark-report.md
│   │   ├── benchmark-trace.jsonl
│   │   ├── benchmark-junit.xml
│   │   ├── forensic-assertions.json
│   │   ├── compliance-report.json
│   │   ├── compliance-report.md
│   │   └── benchmark-dbs/
│   └── ...
├── benchmark-report.json             # Legacy flat (backward compatible)
└── ...
```

## Artifact Contract
Generated under `artifacts/`:

### v1 Artifacts
- `benchmark-report.json` — structured scoring results (schema version 1.1)
- `benchmark-report.md` — human-readable markdown summary
- `benchmark-junit.xml` — raw pytest junit output

### v1.1 Artifacts
- `benchmark-trace.jsonl` — structured trace event log (one JSON event per line)
- `forensic-assertions.json` — SQL assertion results with pass/fail and evidence
- `benchmark-dbs/` — file-backed SQLite databases used for forensic SQL queries

### v1.2 Artifacts
- `compliance-report.json` — structured compliance results from safety packs (null-content traps, PII red-team)
- `compliance-report.md` — human-readable markdown compliance summary

### v1.3 Artifacts
- `chaos-report.json` — structured chaos/resilience results (fault profiles, per-scenario resilience scores, state integrity checks)
- `chaos-report.md` — human-readable markdown chaos summary with fault matrix and resilience scoring

### Trace Event Format (`benchmark-trace.jsonl`)
Each line is a JSON object with:
- `trace_id` — UUID for the entire trace session
- `run_id` — UUID for this benchmark run
- `scenario_id` — scenario identifier (null for run-level events)
- `event_type` — one of: `benchmark_run_start`, `benchmark_run_end`, `scenario_start`, `scenario_end`, `tool_call`, `assertion_start`, `assertion_result`, `db_snapshot`
- `source` — component that emitted the event
- `timestamp` — UTC ISO timestamp
- `payload` — event-specific data

### Forensic Assertion Format (`forensic-assertions.json`)
Top-level fields:
- `run_id` — benchmark run identifier
- `generated_at` — UTC ISO timestamp
- `assertions` — list of assertion results
- `summary` — `{"pass": N, "fail": M, "total": N+M}`

Each assertion result:
- `assertion_id` — e.g., `inventory_conservation_v1`
- `status` — `pass` or `fail`
- `severity` — `critical`, `warning`, or `info`
- `sql` — the SQL query executed
- `result` — query output data
- `evidence` — human-readable explanation

### Required JSON Per-Scenario Fields
Each scenario record includes:
- `tier`
- `completion`
- `step_accuracy`
- `policy_compliance`
- `hallucinations`
- `tool_calls_total`
- `tool_calls_correct`
- `taxonomy`

### v1.1 Report Top-Level Fields
- `schema_version` — `"1.1"`
- `trace_summary` — aggregated trace event counts and time range
- `forensic_assertions` — list of forensic assertion results

### v1.2 Report Top-Level Fields
- `schema_version` — `"1.2"`
- `safety_summary` — aggregated pass/fail counts for all safety scenarios
- `null_content_results` — per-scenario results for null-content trap evaluations
- `pii_leakage_results` — per-scenario results for PII red-team evaluations

### v1.3 Report Top-Level Fields
- `schema_version` — `"1.3"`
- `chaos_summary` — fault injection summary (profiles used, faults injected, recovery outcomes)
- `resilience_summary` — aggregated resilience scores with per-scenario breakdown

### v1.4 Artifacts
- `network-seed-report.json` — federated seed report with per-library summaries, batch coverage, and validation results

### v1.4 Manifest Scenario Fields
- `requires_federated_seed` — boolean indicating scenario needs federated topology
- `expected_source_library` — expected spoke library for ILL request scenarios
- `network_lookup_required` — boolean indicating scenario requires network holdings resolution

### v1.5 Artifacts
- `runs/index.json` — run index with metadata for all benchmark runs (schema version 1.5)
- `runs/<run_id>/` — per-run artifact directory containing all outputs from that run

### v1.5 Report Top-Level Fields
- `schema_version` — `"1.5"` (when generated via orchestrator with `--run-id`)
- All v1.3 fields preserved; schema version remains `"1.3"` for direct CLI runs without `--run-id`

### v1.5 Run Index Schema (`runs/index.json`)
- `schema_version` — `"1.5"`
- `runs[]` — array of run metadata objects, each with:
  - `run_id` — unique run identifier
  - `suite` — benchmark suite name
  - `status` — lifecycle state (`queued`, `running`, `passed`, `failed`)
  - `started_at` — UTC ISO timestamp
  - `completed_at` — UTC ISO timestamp (null until complete)
  - `artifact_dir` — path to run's artifact directory
  - `report_path` — path to benchmark-report.json (null until complete)
  - `trace_path` — path to benchmark-trace.jsonl (null until complete)
  - `artifact_paths[]` — list of all artifact file paths relative to artifact_dir

## Manifest-Driven Benchmark Metadata
Canonical manifest:
- `tests/scenarios/scenario_manifest.json`

Manifest controls:
- scenario ID
- tier assignment
- expected steps
- policy checks
- expected tool calls
- taxonomy hints

## Forensic Assertions (v1.1)
Two SQL assertions are executed against benchmark databases:

1. **`inventory_conservation_v1`** (critical) — verifies total book instances == sum of status-bucketed counts (available + checked_out + transit + other)
2. **`financial_integrity_v1`** (critical) — verifies per-patron fine ledgers balance (charges == paid + waived + outstanding)

Assertions use file-backed SQLite databases created by test fixtures when `BENCHMARK_DB_DIR` environment variable is set. The benchmark runner sets this automatically for `scenarios` and `full` suites.

## CI Path
Workflow:
- `.github/workflows/ci.yml`

Baseline gates:
- `uv run pytest -q`
- `uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q`
- `uv run pytest --no-cov tests/scenarios/test_trace_schema.py -q`
- `uv run pytest --no-cov tests/scenarios/test_forensic_assertions.py -q`
- `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

Artifacts are uploaded from `artifacts/**`.

## Troubleshooting
1. Manifest mismatch (scenario IDs not resolved):
```bash
uv run python scripts/benchmark_run.py --suite scenarios --manifest tests/scenarios/scenario_manifest.json
```
2. Synthetic policy violation:
```bash
uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q
rg -n "1984|George Orwell|Jane Austen|Dune|The Martian|Project Hail Mary" tests/scenarios
```
3. ADK summary unavailable in report:
- Ensure workspace dependencies are synced with `uv sync --all-packages`.
- Validate import path:
```bash
uv run python -c "from agents.benchmark_runner import BenchmarkRunner; print('ok')"
```
4. Forensic assertions missing from report:
- Verify `BENCHMARK_DB_DIR` was set during pytest execution.
- Check that `artifacts/benchmark-dbs/catalog.db` and `artifacts/benchmark-dbs/circulation.db` exist.
- Run assertions manually:
```bash
cd scripts && uv run python -c "from forensic_assertions import run_forensic_assertions; from pathlib import Path; print(run_forensic_assertions(Path('../artifacts/benchmark-dbs')))"
```

5. Run index missing or corrupt:
- Verify `artifacts/runs/` directory exists.
- Check `artifacts/runs/index.json` for valid JSON.
- Re-create by posting a new run via `POST /benchmark/runs`.
6. Run stuck in `running` status:
- The benchmark subprocess may have crashed. Check server logs.
- Known limitation: server restarts do not auto-recover running tasks.

## V1.6 Operator Routes (Frontend)

The v1.6 frontend adds route-based navigation for operator workflows. All routes use hash-based URLs.

### Route Map
| Route | Purpose |
|-------|---------|
| `/#/chat` | Default — 3-panel chat interface (scenario sidebar + chat + forensic ledger) |
| `/#/runs` | Benchmark run list with status badges and "New Benchmark Run" button |
| `/#/runs/:runId` | Run detail — metadata, status polling, links to report/trace |
| `/#/reports/:runId` | Full benchmark report view (metrics, scenarios, forensic assertions) |
| `/#/replay/:runId` | Trace event timeline with color-coded event markers |

### Frontend Commands
```bash
# Build frontend
cd frontend && ng build

# Run E2E tests (builds automatically)
cd frontend && npm run e2e

# Serve for development
cd frontend && ng serve
```

### Local Preflight
```bash
scripts/run_local_alpha.sh
```
Checks prerequisites (uv, node, npm), port availability (8000-8004, 4200), service health, and frontend build state.

## V1.7 Multi-Instance Federation Commands
```bash
# Spoke catalog seeding tests
uv run pytest tests/scenarios/test_spoke_catalog_seeding.py -q

# Direct URL HTTP client tests
uv run pytest tests/scenarios/test_registry_spoke_resolution.py -q

# Live federation integration tests (in-process multi-catalog)
uv run pytest tests/scenarios/test_live_federation.py -q

# v1.4 backward compatibility (fixture-based)
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q

# Provision spoke databases locally
uv run python scripts/seed_network.py --mode provision

# Docker multi-instance startup
docker compose up --build -d

# Seed spoke catalogs and registry in Docker
bash scripts/seed_docker_federation.sh

# Verify spoke catalog health
curl -sf http://127.0.0.1:8011/library/info | python3 -m json.tool  # Mastodon
curl -sf http://127.0.0.1:8012/library/info | python3 -m json.tool  # Mammoth
curl -sf http://127.0.0.1:8013/library/info | python3 -m json.tool  # Ivory
curl -sf http://127.0.0.1:8014/library/info | python3 -m json.tool  # Tusk
```

### V1.7 Docker Port Layout
| Port | Service | Library |
|------|---------|---------|
| 8001 | catalog | Hanno Memorial (hub) |
| 8011 | catalog-mastodon | Mastodon Institute |
| 8012 | catalog-mammoth | Mammoth Valley |
| 8013 | catalog-ivory | Ivory University |
| 8014 | catalog-tusk | Tusk Conservatory |

## Evidence Commands
```bash
uv run pytest tests/scenarios -q
uv run pytest tests/scenarios/test_trace_schema.py -q
uv run pytest tests/scenarios/test_forensic_assertions.py -q
uv run pytest agents/tests/integration/test_benchmark_runner.py -q
uv run python scripts/benchmark_run.py --suite scenarios --include-adk

# V1.2 safety pack evidence
uv run pytest tests/scenarios/test_null_content_trap.py -q
uv run pytest tests/scenarios/test_honey_pot_redteam.py -q
uv run pytest tests/scenarios/test_compliance_report_schema.py -q

# V1.3 chaos & resilience evidence
uv run pytest tests/scenarios/test_chaos_fault_injection.py -q
uv run pytest tests/scenarios/test_resilience_scoring.py -q
uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q
uv run pytest tests/scenarios/test_chaos_report_schema.py -q

# V1.4 federated topology evidence
uv run pytest tests/scenarios/test_federated_seed_manifest.py -q
uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q
uv run python scripts/seed_manifest_validator.py --check-only

# V1.5 run control plane evidence
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q

# V1.6 frontend operator routes evidence
cd frontend && ng build
cd frontend && npm run e2e

# V1.7 multi-instance federation evidence
uv run pytest tests/scenarios/test_spoke_catalog_seeding.py -q
uv run pytest tests/scenarios/test_registry_spoke_resolution.py -q
uv run pytest tests/scenarios/test_live_federation.py -q
uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q
```
