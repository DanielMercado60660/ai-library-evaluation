"""Report builder for v2.4 open-ended benchmark runs.

Produces a v1.5-compatible report with an additional ``benchmark_details``
key containing per-interaction results and aggregate statistics.
"""

from collections import defaultdict
from datetime import datetime, UTC
from typing import Any

from agents.benchmark_config import BenchmarkConfig, InteractionResult
from agents.benchmark_session_executor import BenchmarkAggregateMetrics


def build_benchmark_report(
    run_id: str,
    results: list[InteractionResult],
    metrics: BenchmarkAggregateMetrics,
    config: BenchmarkConfig,
    model_name: str = "unknown",
    suite: str = "benchmark",
    wall_clock_seconds: float = 0.0,
) -> dict[str, Any]:
    """Build v1.5-compatible report with ``benchmark_details`` extension."""
    total = metrics.total_interactions
    completed = metrics.completed
    errored = metrics.errored

    completion_rate_percent = (
        (completed / total * 100) if total > 0 else 0.0
    )
    tool_precision_percent = (
        (metrics.tool_engaged_count / completed * 100) if completed > 0 else 0.0
    )
    policy_compliance_percent = (
        ((completed - metrics.hallucination_count) / completed * 100)
        if completed > 0
        else 0.0
    )
    hallucinations = metrics.hallucination_count
    avg_response_time_ms = (
        metrics.total_response_time_ms / completed if completed > 0 else 0.0
    )

    summary = {
        "total": total,
        "passed": completed,
        "failed": errored,
        "errors": errored,
        "skipped": max(0, total - completed - errored),
        "completion_rate_percent": round(completion_rate_percent, 4),
        "policy_compliance_percent": round(policy_compliance_percent, 4),
        "tool_precision_percent": round(tool_precision_percent, 4),
        "hallucinations": hallucinations,
    }

    scenarios = _build_domain_scenarios(results, metrics)

    benchmark_details = {
        "config": config.model_dump(mode="json"),
        "total_interactions": total,
        "completed": completed,
        "errored": errored,
        "timed_out": metrics.timed_out,
        "avg_response_time_ms": round(avg_response_time_ms, 1),
        "tool_engagement_rate": round(tool_precision_percent, 4),
        "error_rate": round(
            (errored / total * 100) if total > 0 else 0.0, 4
        ),
        "domain_breakdown": metrics.domain_breakdown,
        "wall_clock_seconds": round(wall_clock_seconds, 1),
        "interactions": [r.model_dump(mode="json") for r in results],
    }

    return {
        "schema_version": "1.5",
        "run_mode": "benchmark",
        "suite": suite,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "model_name": model_name,
        "summary": summary,
        "scenarios": scenarios,
        "benchmark_details": benchmark_details,
        "eval_details": {},
        "forensic_assertions": [],
        "chaos_summary": {},
        "resilience_summary": {},
    }


def _build_domain_scenarios(
    results: list[InteractionResult],
    metrics: BenchmarkAggregateMetrics,
) -> list[dict[str, Any]]:
    """Group interactions by domain into pseudo-scenario entries.

    This allows the existing comparison infrastructure (which expects
    a ``scenarios`` list) to work with benchmark reports.
    """
    domain_map = {
        "catalog": 1,
        "circulation": 2,
        "ill": 3,
    }
    buckets: dict[str, list[InteractionResult]] = defaultdict(list)
    for r in results:
        buckets[r.expected_domain].append(r)

    scenarios: list[dict[str, Any]] = []
    for domain, items in buckets.items():
        total = len(items)
        completed = sum(1 for r in items if r.status == "completed")
        hallucinations = sum(1 for r in items if r.hallucination_detected)
        tool_engaged = sum(1 for r in items if r.tool_engaged)

        completion = completed / total if total > 0 else 0.0
        tool_precision = tool_engaged / completed if completed > 0 else 0.0
        policy_compliance = (
            (completed - hallucinations) / completed if completed > 0 else 0.0
        )

        scenarios.append({
            "scenario_id": f"benchmark_{domain}",
            "status": "passed" if completed == total else "failed",
            "tier": domain_map.get(domain, 0),
            "completion": round(completion, 4),
            "step_accuracy": round(completion, 4),
            "hallucinations": hallucinations,
            "tool_calls_total": tool_engaged,
            "tool_calls_correct": tool_engaged,
            "tool_precision": round(tool_precision, 4),
            "policy_compliance": round(policy_compliance, 4),
            "duration_ms": round(sum(r.duration_ms for r in items), 1),
            "taxonomy": "benchmark",
        })

    return scenarios


def build_benchmark_markdown(report: dict[str, Any]) -> str:
    """Generate a markdown summary from a benchmark report."""
    summary = report.get("summary", {})
    details = report.get("benchmark_details", {})
    scenarios = report.get("scenarios", [])

    lines = [
        "# Benchmark Run Summary",
        "",
        f"- **Run ID**: {report.get('run_id', 'N/A')}",
        f"- **Model**: {report.get('model_name', 'N/A')}",
        f"- **Mode**: benchmark",
        f"- **Generated**: {report.get('generated_at', 'N/A')}",
        "",
        "## Aggregate Metrics",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total interactions | {summary.get('total', 0)} |",
        f"| Completed | {summary.get('passed', 0)} |",
        f"| Errors | {summary.get('errors', 0)} |",
        f"| Completion rate | {summary.get('completion_rate_percent', 0):.1f}% |",
        f"| Tool engagement | {summary.get('tool_precision_percent', 0):.1f}% |",
        f"| Policy compliance | {summary.get('policy_compliance_percent', 0):.1f}% |",
        f"| Hallucinations | {summary.get('hallucinations', 0)} |",
        f"| Avg response time | {details.get('avg_response_time_ms', 0):.0f}ms |",
        f"| Wall clock | {details.get('wall_clock_seconds', 0):.1f}s |",
        "",
        "## Domain Breakdown",
        "",
        "| Domain | Status | Completion | Tool Precision | Hallucinations |",
        "|--------|--------|-----------|---------------|---------------|",
    ]

    for s in scenarios:
        lines.append(
            f"| {s['scenario_id']} | {s['status']} | "
            f"{s['completion']:.0%} | {s['tool_precision']:.0%} | "
            f"{s['hallucinations']} |"
        )

    lines.append("")
    return "\n".join(lines)
