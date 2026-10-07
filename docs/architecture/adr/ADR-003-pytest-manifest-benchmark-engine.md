# ADR-003: Pytest + Manifest Benchmark Engine

## Status

Accepted

## Context

The evaluation architecture document (`docs/architecture/EVALUATION.md`) originally specified a class-based scenario engine with custom runner abstractions. As implementation progressed, the team needed to decide between building a custom engine or leveraging standard Python test tooling.

Two approaches were considered:

- **Option A (Class-Based Engine)**: Custom scenario runner hierarchy with explicit step execution, state management, and scoring integration. More control over execution flow.
- **Option B (Pytest + Manifest)**: Use pytest as the scenario runner with a JSON manifest providing per-scenario metadata. Parse JUnit XML output for deterministic scoring. Benchmark report generation via `scripts/benchmark_run.py`.

## Decision

We chose **Option B (Pytest + Manifest)**. Scenarios are standard pytest test functions organized by tier (`test_tier1_catalog.py`, `test_tier2_circulation.py`, `test_tier3_ill_a2a.py`). The scenario manifest (`tests/scenarios/scenario_manifest.json`) provides per-scenario metadata including tier, expected steps, taxonomy hints, and policy checks.

`scripts/benchmark_run.py` orchestrates the benchmark: runs pytest with `--junitxml`, parses the output, computes deterministic metrics, and generates JSON/Markdown reports with trace summaries and forensic assertions.

## Consequences

**Positive:**
- Leverages standard Python test tooling with no custom runner to maintain.
- CI integration is trivial via pytest's built-in JUnit output.
- Manifest-driven scoring is declarative and easy to extend with new scenario metadata fields.
- Test fixtures, parametrization, and async support come for free from pytest.

**Trade-offs:**
- Scenario flow is implicit in test function structure rather than explicit step objects.
- Custom metrics require post-processing of JUnit XML rather than in-process instrumentation.
- The manifest must be kept in sync with test functions (enforced by `test_v1_scenarios_no_skip.py`).

**References:** `tests/scenarios/scenario_manifest.json`, `scripts/benchmark_run.py`, `tests/scenarios/test_benchmark_scoring.py`, `docs/architecture/EVALUATION.md`
