# Performance Budgets for Local Alpha (v2.0)

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Measurable performance guardrails for local development environments
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Related Workstream: infrastructure-services, evaluation-harness

## Purpose

Defines stability-grade performance budgets for the local alpha stack. These are **guardrails, not production SLOs** — generous thresholds that catch regressions without penalizing normal dev machine variance.

## Budget Thresholds

### Health Endpoint Latency (In-Process ASGI)
- **Budget**: < 2000ms per endpoint
- **Measurement**: `ASGITransport` round-trip time (no network overhead)
- **Services**: catalog, circulation, ill, registry (4 services)
- **Rationale**: Generous threshold for local SQLite + in-process calls; catches broken imports or middleware loops

### Individual Test Scenario
- **Budget**: < 30s per scenario
- **Measurement**: JUnit XML `time` attribute from pytest `--junitxml`
- **Rationale**: Single scenarios exceeding 30s indicate blocking I/O or infinite loops

### Full Test Suite
- **Budget**: < 120s for all collected tests
- **Measurement**: Total pytest wall-clock time
- **Rationale**: Fast feedback loop is critical for development velocity

### Performance Smoke Total
- **Budget**: < 10s for `perf_smoke.py` full run
- **Scope**: 4 health checks + report generation verification
- **Rationale**: Quick enough to run on every CI pipeline execution

### Report Generation
- **Budget**: < 5000ms to load and parse benchmark report JSON
- **Measurement**: `time.perf_counter()` around JSON load
- **Rationale**: Catches bloated report files or broken JSON

## Measurement Strategy

1. **ASGITransport for determinism**: All in-process measurements use `httpx.ASGITransport` to avoid network variance, port conflicts, and startup delays. Same pattern as test fixtures in `conftest.py`.

2. **Auth headers required**: Since v1.8 added `ServiceAuthMiddleware`, all health checks include `X-Service-Token: dev-token-ai-librarian`.

3. **JSON report output**: `scripts/perf_smoke.py` writes a structured JSON report with per-check results, violation details, and budget metadata.

## Enforcement

- **CI**: `uv run python scripts/perf_smoke.py --strict` — non-zero exit on any budget violation
- **Local**: `uv run python scripts/perf_smoke.py` — prints results without failing (visibility mode)
- **Report artifact**: `artifacts/perf-smoke-report.json` uploaded in CI

## Budget Constants (Code Reference)

```python
HEALTH_ENDPOINT_BUDGET_MS = 2000
REPORT_GENERATION_BUDGET_MS = 5000
PERF_SMOKE_TOTAL_BUDGET_MS = 10000
```

Defined in `scripts/perf_smoke.py` and validated by `tests/scenarios/test_performance_budgets.py`.
