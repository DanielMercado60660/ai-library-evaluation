#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SUITE="${1:-scenarios}"
CHAOS_PROFILE="${CHAOS_PROFILE:-}"

cd "$REPO_ROOT"

echo "[v1.5] Syncing dependencies"
uv sync --all-packages

echo "[v1.5] Running baseline regression"
uv run pytest -q

echo "[v1.5] Running synthetic guardrails"
uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q

echo "[v1.5] Running trace schema tests"
uv run pytest --no-cov tests/scenarios/test_trace_schema.py -q

echo "[v1.5] Running forensic assertion tests"
uv run pytest --no-cov tests/scenarios/test_forensic_assertions.py -q

echo "[v1.5] Running null-content trap tests"
uv run pytest --no-cov tests/scenarios/test_null_content_trap.py -q

echo "[v1.5] Running honey pot red-team tests"
uv run pytest --no-cov tests/scenarios/test_honey_pot_redteam.py -q

echo "[v1.5] Running compliance report schema tests"
uv run pytest --no-cov tests/scenarios/test_compliance_report_schema.py -q

echo "[v1.5] Running safety pack scoring tests"
uv run pytest --no-cov tests/scenarios/test_safety_pack_scoring.py -q

echo "[v1.5] Running chaos controller tests"
uv run pytest --no-cov tests/scenarios/test_chaos_fault_injection.py -q

echo "[v1.5] Running resilience scoring tests"
uv run pytest --no-cov tests/scenarios/test_resilience_scoring.py -q

echo "[v1.5] Running chaos integration scenarios"
uv run pytest --no-cov tests/scenarios/test_tier3_ill_a2a_chaos.py -q

echo "[v1.5] Running chaos report schema tests"
uv run pytest --no-cov tests/scenarios/test_chaos_report_schema.py -q

echo "[v1.5] Running run control plane tests"
uv run pytest --no-cov agents/tests/integration/test_run_index_integrity.py -q
uv run pytest --no-cov agents/tests/integration/test_benchmark_run_lifecycle.py -q

echo "[v1.5] Running benchmark suite: $SUITE"
CHAOS_ARG=""
if [ -n "$CHAOS_PROFILE" ]; then
    CHAOS_ARG="--chaos-profile $CHAOS_PROFILE"
fi
uv run python scripts/benchmark_run.py --suite "$SUITE" --include-adk $CHAOS_ARG

echo "[v1.5] Verifying artifacts"
test -f artifacts/benchmark-trace.jsonl && echo "  benchmark-trace.jsonl OK" || echo "  benchmark-trace.jsonl MISSING"
test -f artifacts/forensic-assertions.json && echo "  forensic-assertions.json OK" || echo "  forensic-assertions.json MISSING"
test -f artifacts/compliance-report.json && echo "  compliance-report.json OK" || echo "  compliance-report.json MISSING"
test -f artifacts/compliance-report.md && echo "  compliance-report.md OK" || echo "  compliance-report.md MISSING"

if [ -n "$CHAOS_PROFILE" ]; then
    test -f artifacts/chaos-report.json && echo "  chaos-report.json OK" || echo "  chaos-report.json MISSING"
    test -f artifacts/chaos-report.md && echo "  chaos-report.md OK" || echo "  chaos-report.md MISSING"
fi

# Verify run index if runs directory exists (v1.5 run control plane)
if [ -d "artifacts/runs" ]; then
    echo "[v1.5] Verifying run index"
    test -f artifacts/runs/index.json && echo "  index.json OK" || echo "  index.json MISSING"
fi

echo "[v1.5] Benchmark artifacts available under artifacts/"
