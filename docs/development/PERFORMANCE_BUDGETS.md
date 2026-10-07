# Performance budgets

These are local harness thresholds enforced by `scripts/perf_smoke.py`.
They measure in-process ASGI responses and report generation, excluding
network latency and model inference.

| Check | Budget |
|---|---:|
| Health Endpoint, per service | 2000 ms |
| Report generation | 5000 ms |
| Total smoke run | 10000 ms |

Run from the repository root:

```bash
uv run python scripts/perf_smoke.py --strict
uv run pytest tests/scenarios/test_performance_budgets.py -q
```

The generated `artifacts/perf-smoke-report.json` records measurements and
violations. These budgets are regression checks, not live LLM latency claims.
