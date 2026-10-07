# Benchmark runbook

Run from the repository root after `uv sync --frozen --all-packages`.

## Deterministic harness

```bash
uv run python scripts/benchmark_run.py --suite smoke
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
```

The first command checks a small catalog/guardrail slice. The second runs the
scenario suite and adds the deterministic ADK topology adapter. Neither invokes
live Gemini inference. The adapter maps scenarios to configured agents and
synthetic tool traces; passing its checks does not establish model competence.

Reports are written under `artifacts/`: JSON and Markdown scores, JUnit output,
JSONL traces, safety/compliance results, and forensic assertion evidence where
applicable. Keep these generated files local. Use `--artifacts-dir` to select a
separate destination for a comparison run.

## Live evaluation

Start the local stack with your Google API key configured, then use the
Assistant and Benchmark Runs views. The agent service exposes separate
evaluation and benchmark executors. Keep `EVAL_SHORTCUTS_ENABLED=false` for
model inference and inspect each run's mode, model, trace, and final database
state before treating it as model evidence.

The repository ships no model leaderboard claims. Deterministic fixture
success and mocked browser tests validate the platform, not a model's ability
to operate a library. Automated multi-turn adversarial evaluation remains a
research direction; see [the project goal](../../ProjectGoal.md).

## Failure analysis

Inspect the report taxonomy, trace events, and SQL assertions together. Compare
identical scenario sets and fault profiles across runs. For artifact backup and
restore, see the [recovery runbook](RECOVERY_AND_ROLLBACK_RUNBOOK.md).
