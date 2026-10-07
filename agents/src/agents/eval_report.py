"""Eval report builder — maps EvalScenarioResult → v1.5 benchmark report schema.

Produces a report compatible with the existing frontend and benchmark
comparison infrastructure while adding ``eval_details`` with per-step
breakdown.
"""

from datetime import datetime, UTC
from typing import Any

from agents.eval_executor import EvalScenarioResult


def build_eval_report(
    run_id: str,
    scenario_results: list[EvalScenarioResult],
    model_name: str = "unknown",
    suite: str = "scenarios",
) -> dict[str, Any]:
    """Build a v1.5-compatible benchmark report from eval results.

    Args:
        run_id: The benchmark run identifier.
        scenario_results: List of per-scenario eval results.
        model_name: Name of the model used.
        suite: Suite identifier.

    Returns:
        Report dict compatible with ``artifacts/benchmark-report.json``.
    """
    scenarios: list[dict[str, Any]] = []
    eval_details: dict[str, dict[str, Any]] = {}

    total = len(scenario_results)
    passed = 0
    failed = 0
    total_tool_calls = 0
    total_assertions = 0
    total_assertions_passed = 0

    for sr in scenario_results:
        status = "passed" if sr.passed else "failed"
        if sr.passed:
            passed += 1
        else:
            failed += 1

        total_assertions += sr.total_assertions
        total_assertions_passed += sr.passed_assertions

        # Count tool calls across steps
        scenario_tool_calls = sum(
            len(step.tool_calls_observed) for step in sr.steps
        )
        total_tool_calls += scenario_tool_calls

        # Compute per-scenario metrics
        step_count = len(sr.steps)
        steps_passed = sum(1 for s in sr.steps if s.passed)
        completion = steps_passed / step_count if step_count > 0 else 0.0

        # Count content-not-contains violations as hallucinations
        hallucinations = sum(
            1
            for step in sr.steps
            for a in step.assertions
            if a.assertion_type == "content_not_contains" and not a.passed
        )

        # Tool precision: fraction of expected tool calls that were observed
        expected_tool_total = sum(
            len(step.tool_calls_observed)  # observed out of expected
            for step in sr.steps
        )
        tool_precision = 1.0  # default when no tool expectations
        if scenario_tool_calls > 0:
            matched_tool_assertions = sum(
                1
                for step in sr.steps
                for a in step.assertions
                if a.assertion_type == "tool_call" and a.passed
            )
            total_tool_assertions = sum(
                1
                for step in sr.steps
                for a in step.assertions
                if a.assertion_type == "tool_call"
            )
            tool_precision = (
                matched_tool_assertions / total_tool_assertions
                if total_tool_assertions > 0
                else 1.0
            )

        # Policy compliance: all assertions that are NOT tool_call
        policy_assertions = [
            a
            for step in sr.steps
            for a in step.assertions
            if a.assertion_type != "tool_call"
        ]
        policy_compliance = (
            sum(1 for a in policy_assertions if a.passed) / len(policy_assertions)
            if policy_assertions
            else 1.0
        )

        scenario_entry = {
            "scenario_id": sr.scenario_id,
            "status": status,
            "tier": 0,  # tier is not in eval results; frontend can join with manifest
            "completion": round(completion, 4),
            "step_accuracy": round(completion, 4),
            "hallucinations": hallucinations,
            "tool_calls_total": scenario_tool_calls,
            "tool_precision": round(tool_precision, 4),
            "policy_compliance": round(policy_compliance, 4),
            "duration_ms": round(sr.duration_ms, 1),
            "taxonomy": "eval",
        }
        scenarios.append(scenario_entry)

        # Build eval_details per scenario
        step_details: list[dict[str, Any]] = []
        for step in sr.steps:
            step_details.append({
                "step_id": step.step_id,
                "order": step.order,
                "patron_message": step.patron_message,
                "agent_response": step.agent_response,
                "tool_calls_observed": step.tool_calls_observed,
                "passed": step.passed,
                "duration_ms": round(step.duration_ms, 1),
                "error": step.error,
                "assertions": [
                    {
                        "type": a.assertion_type,
                        "passed": a.passed,
                        "details": a.details,
                    }
                    for a in step.assertions
                ],
            })

        eval_details[sr.scenario_id] = {
            "scenario_id": sr.scenario_id,
            "passed": sr.passed,
            "total_assertions": sr.total_assertions,
            "passed_assertions": sr.passed_assertions,
            "duration_ms": round(sr.duration_ms, 1),
            "steps": step_details,
        }

    # Aggregate summary
    overall_completion = passed / total if total > 0 else 0.0
    overall_assertions_pct = (
        total_assertions_passed / total_assertions
        if total_assertions > 0
        else 0.0
    )

    report: dict[str, Any] = {
        "schema_version": "1.5",
        "run_mode": "eval",
        "suite": suite,
        "generated_at": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "model_name": model_name,
        "summary": {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": 0,
            "skipped": 0,
            "completion_rate": round(overall_completion, 4),
            "assertion_pass_rate": round(overall_assertions_pct, 4),
        },
        "scenarios": scenarios,
        "eval_details": eval_details,
        "forensic_assertions": [],
        "chaos_summary": {},
        "resilience_summary": {},
    }

    return report


def build_eval_markdown(report: dict[str, Any]) -> str:
    """Generate a markdown summary from an eval report."""
    summary = report.get("summary", {})
    scenarios = report.get("scenarios", [])

    lines = [
        "# Eval Run Summary",
        "",
        f"- **Run ID**: {report.get('run_id', 'N/A')}",
        f"- **Model**: {report.get('model_name', 'N/A')}",
        f"- **Mode**: {report.get('run_mode', 'eval')}",
        f"- **Generated**: {report.get('generated_at', 'N/A')}",
        "",
        "## Results",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total scenarios | {summary.get('total', 0)} |",
        f"| Passed | {summary.get('passed', 0)} |",
        f"| Failed | {summary.get('failed', 0)} |",
        f"| Completion rate | {summary.get('completion_rate', 0):.1%} |",
        f"| Assertion pass rate | {summary.get('assertion_pass_rate', 0):.1%} |",
        "",
        "## Scenarios",
        "",
        "| Scenario | Status | Completion | Tool Precision | Hallucinations |",
        "|----------|--------|-----------|---------------|---------------|",
    ]

    for s in scenarios:
        lines.append(
            f"| {s['scenario_id']} | {s['status']} | "
            f"{s['completion']:.0%} | {s['tool_precision']:.0%} | "
            f"{s['hallucinations']} |"
        )

    lines.append("")
    return "\n".join(lines)
