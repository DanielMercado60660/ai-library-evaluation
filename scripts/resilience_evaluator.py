"""Resilience scoring and chaos report generation for v1.3 benchmark."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


# Scoring weights for resilience composite score.
WEIGHT_RECOVERY = 0.35
WEIGHT_BUDGET = 0.20
WEIGHT_DEGRADATION = 0.20
WEIGHT_STATE_INTEGRITY = 0.25


@dataclass(slots=True)
class ResilienceMetrics:
    """Per-scenario resilience evaluation result."""

    scenario_id: str
    fault_profile: str
    recovery_success: bool
    retry_attempts: int
    retry_budget_respected: bool
    degraded_mode_used: bool
    state_integrity_preserved: bool
    resilience_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ChaosReport:
    """Complete chaos/resilience report for a benchmark run."""

    report_version: str = "1.3"
    run_id: str = field(default_factory=lambda: str(uuid4()))
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    fault_profiles: list[dict[str, Any]] = field(default_factory=list)
    scenario_results: list[dict[str, Any]] = field(default_factory=list)
    resilience_failures: list[dict[str, Any]] = field(default_factory=list)
    state_integrity_checks: list[dict[str, Any]] = field(default_factory=list)
    aggregate: dict[str, Any] = field(default_factory=dict)


class ResilienceEvaluator:
    """Evaluate resilience from chaos test outcomes."""

    def evaluate_scenario(
        self,
        *,
        scenario_id: str,
        test_status: str,
        fault_profile: str,
        chaos_log: list[dict[str, Any]],
        max_budget: int,
        retry_attempts: int = 0,
        forensic_status: str = "pass",
    ) -> ResilienceMetrics:
        """Score a single scenario's resilience under faults."""
        recovery = test_status == "passed"
        budget_ok = retry_attempts <= max_budget
        degraded = len(chaos_log) > 0  # Faults were injected → system used degraded path
        state_ok = forensic_status == "pass"

        score = (
            WEIGHT_RECOVERY * (1.0 if recovery else 0.0)
            + WEIGHT_BUDGET * (1.0 if budget_ok else 0.0)
            + WEIGHT_DEGRADATION * (1.0 if degraded else 0.0)
            + WEIGHT_STATE_INTEGRITY * (1.0 if state_ok else 0.0)
        )

        return ResilienceMetrics(
            scenario_id=scenario_id,
            fault_profile=fault_profile,
            recovery_success=recovery,
            retry_attempts=retry_attempts,
            retry_budget_respected=budget_ok,
            degraded_mode_used=degraded,
            state_integrity_preserved=state_ok,
            resilience_score=round(score, 4),
        )

    def aggregate_summary(self, metrics: list[ResilienceMetrics]) -> dict[str, Any]:
        """Aggregate resilience metrics across all chaos scenarios."""
        if not metrics:
            return {
                "total_scenarios": 0,
                "avg_resilience_score": 0.0,
                "recovery_rate": 0.0,
                "budget_compliance_rate": 0.0,
                "state_integrity_rate": 0.0,
            }

        total = len(metrics)
        return {
            "total_scenarios": total,
            "avg_resilience_score": round(
                sum(m.resilience_score for m in metrics) / total, 4
            ),
            "recovery_rate": round(
                sum(1 for m in metrics if m.recovery_success) / total, 4
            ),
            "budget_compliance_rate": round(
                sum(1 for m in metrics if m.retry_budget_respected) / total, 4
            ),
            "state_integrity_rate": round(
                sum(1 for m in metrics if m.state_integrity_preserved) / total, 4
            ),
        }


def build_chaos_report(
    *,
    run_id: str,
    fault_profiles: list[dict[str, Any]],
    metrics: list[ResilienceMetrics],
    evaluator: ResilienceEvaluator,
) -> ChaosReport:
    """Build a complete ChaosReport from evaluation results."""
    failures = [m for m in metrics if not m.recovery_success]
    state_issues = [m for m in metrics if not m.state_integrity_preserved]

    return ChaosReport(
        run_id=run_id,
        fault_profiles=fault_profiles,
        scenario_results=[m.to_dict() for m in metrics],
        resilience_failures=[
            {"scenario_id": m.scenario_id, "fault_profile": m.fault_profile,
             "evidence": f"Recovery failed (score={m.resilience_score})"}
            for m in failures
        ],
        state_integrity_checks=[
            {"scenario_id": m.scenario_id, "status": "fail",
             "evidence": "State integrity violated under fault injection"}
            for m in state_issues
        ],
        aggregate=evaluator.aggregate_summary(metrics),
    )


def write_chaos_json(report: ChaosReport, path: Path) -> None:
    """Write chaos report as JSON."""
    path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")


def write_chaos_markdown(report: ChaosReport, path: Path) -> None:
    """Write chaos report as Markdown."""
    lines = [
        "# Chaos & Resilience Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Generated: {report.generated_at}",
        f"- Report Version: {report.report_version}",
        "",
        "## Executive Summary",
    ]

    agg = report.aggregate
    if agg:
        lines.extend([
            f"- Total Chaos Scenarios: {agg.get('total_scenarios', 0)}",
            f"- Avg Resilience Score: {agg.get('avg_resilience_score', 0.0)}",
            f"- Recovery Rate: {agg.get('recovery_rate', 0.0)}",
            f"- Budget Compliance: {agg.get('budget_compliance_rate', 0.0)}",
            f"- State Integrity: {agg.get('state_integrity_rate', 0.0)}",
        ])

    lines.append("")
    lines.append("## Fault Matrix")
    lines.append("")
    lines.append("| Scenario | Profile | Score | Recovery | Budget OK | State OK |")
    lines.append("|----------|---------|-------|----------|-----------|----------|")

    for result in report.scenario_results:
        lines.append(
            f"| {result['scenario_id']} "
            f"| {result['fault_profile']} "
            f"| {result['resilience_score']} "
            f"| {'Yes' if result['recovery_success'] else 'No'} "
            f"| {'Yes' if result['retry_budget_respected'] else 'No'} "
            f"| {'Yes' if result['state_integrity_preserved'] else 'No'} |"
        )

    if report.resilience_failures:
        lines.append("")
        lines.append("## Resilience Failures")
        for failure in report.resilience_failures:
            lines.append(f"- `{failure['scenario_id']}`: {failure['evidence']}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
