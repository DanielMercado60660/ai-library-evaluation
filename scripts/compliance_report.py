"""Compliance report generator for safety benchmark artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Literal


@dataclass(slots=True)
class ComplianceReport:
    """Structured compliance report combining all safety evaluation results."""

    report_version: str
    run_id: str
    generated_at: str
    overall_status: Literal["pass", "fail"]
    canary_results: list[dict[str, Any]]
    attack_results: list[dict[str, Any]]
    violations: list[dict[str, Any]]
    recommendations: list[str]


def generate_compliance_report(
    *,
    canary_scan_results: list[Any] | None = None,
    null_content_results: list[Any] | None = None,
    run_id: str = "unknown",
) -> ComplianceReport:
    """Assemble all safety results into a compliance report.

    Args:
        canary_scan_results: List of CanaryScanResult dataclass instances.
        null_content_results: List of NullContentResult dataclass instances.
        run_id: Benchmark run identifier.

    Returns:
        ComplianceReport with aggregated safety findings.
    """
    canary_results: list[dict[str, Any]] = []
    attack_results: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    recommendations: list[str] = []

    has_failure = False

    # Process canary scan results (PII leakage).
    if canary_scan_results:
        for result in canary_scan_results:
            entry = {
                "scenario_id": result.scenario_id,
                "attack_type": result.attack_type,
                "status": result.status,
                "leaked_tokens": result.leaked_tokens,
                "evidence": result.evidence,
            }
            attack_results.append(entry)

            if result.status == "fail":
                has_failure = True
                violations.append({
                    "type": "pii_leakage",
                    "scenario_id": result.scenario_id,
                    "severity": "critical",
                    "detail": result.evidence,
                })

    # Process null-content results (fabrication).
    if null_content_results:
        for result in null_content_results:
            entry = {
                "case_id": result.case_id,
                "book_id": result.book_id,
                "request_type": result.request_type,
                "status": result.status,
                "evidence": result.evidence,
            }
            canary_results.append(entry)

            if result.status == "fail":
                has_failure = True
                violations.append({
                    "type": "content_fabrication",
                    "case_id": result.case_id,
                    "severity": "warning",
                    "detail": result.evidence,
                })

    # Generate recommendations based on findings.
    pii_failures = sum(1 for v in violations if v["type"] == "pii_leakage")
    fab_failures = sum(1 for v in violations if v["type"] == "content_fabrication")

    if pii_failures > 0:
        recommendations.append(
            f"PII leakage detected in {pii_failures} scenario(s). "
            "Review agent system prompts for data isolation enforcement."
        )
    if fab_failures > 0:
        recommendations.append(
            f"Content fabrication detected in {fab_failures} case(s). "
            "Strengthen agent refusal behavior for unavailable content."
        )
    if not has_failure:
        recommendations.append("All safety checks passed. No remediation required.")

    return ComplianceReport(
        report_version="1.0",
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
        overall_status="fail" if has_failure else "pass",
        canary_results=canary_results,
        attack_results=attack_results,
        violations=violations,
        recommendations=recommendations,
    )


def write_compliance_json(report: ComplianceReport, path: Path) -> None:
    """Write compliance report as JSON artifact."""
    path.write_text(
        json.dumps(asdict(report), indent=2),
        encoding="utf-8",
    )


def write_compliance_markdown(report: ComplianceReport, path: Path) -> None:
    """Write compliance report as human-readable Markdown artifact."""
    lines = [
        "# Compliance Report",
        "",
        f"- Report Version: {report.report_version}",
        f"- Run ID: `{report.run_id}`",
        f"- Generated At: {report.generated_at}",
        f"- Overall Status: **{report.overall_status.upper()}**",
        "",
        "## Executive Summary",
        "",
        f"- Null-Content Trap Results: {len(report.canary_results)}",
        f"- PII Attack Scenario Results: {len(report.attack_results)}",
        f"- Total Violations: {len(report.violations)}",
        "",
    ]

    # Null-content results.
    lines.append("## Null-Content Trap Results")
    lines.append("")
    if report.canary_results:
        for entry in report.canary_results:
            status_mark = "PASS" if entry["status"] == "pass" else "FAIL"
            lines.append(
                f"- [{status_mark}] `{entry['case_id']}` "
                f"({entry['request_type']}): {entry['evidence']}"
            )
    else:
        lines.append("- No null-content trap results recorded.")
    lines.append("")

    # PII attack results.
    lines.append("## PII Attack Scenario Results")
    lines.append("")
    if report.attack_results:
        for entry in report.attack_results:
            status_mark = "PASS" if entry["status"] == "pass" else "FAIL"
            lines.append(
                f"- [{status_mark}] `{entry['scenario_id']}` "
                f"({entry['attack_type']}): {entry['evidence']}"
            )
    else:
        lines.append("- No PII attack results recorded.")
    lines.append("")

    # Violations.
    lines.append("## Violation Inventory")
    lines.append("")
    if report.violations:
        for v in report.violations:
            identifier = v.get("scenario_id") or v.get("case_id", "unknown")
            lines.append(
                f"- [{v['severity'].upper()}] `{identifier}` "
                f"({v['type']}): {v['detail']}"
            )
    else:
        lines.append("- No violations detected.")
    lines.append("")

    # Recommendations.
    lines.append("## Recommendations")
    lines.append("")
    for rec in report.recommendations:
        lines.append(f"- {rec}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
