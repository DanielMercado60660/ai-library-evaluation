"""Compliance report schema validation tests."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from compliance_report import (  # noqa: E402
    ComplianceReport,
    generate_compliance_report,
    write_compliance_json,
    write_compliance_markdown,
)
from safety_evaluator import NullContentResult  # noqa: E402
from pii_canary_scanner import CanaryScanResult  # noqa: E402


def _make_canary_result(
    scenario_id: str = "test_001",
    status: str = "pass",
    leaked: list[str] | None = None,
) -> CanaryScanResult:
    return CanaryScanResult(
        scenario_id=scenario_id,
        attack_type="direct_extraction",
        status=status,
        leaked_tokens=leaked or [],
        evidence="test evidence",
    )


def _make_null_result(
    case_id: str = "null_trap_001",
    status: str = "pass",
) -> NullContentResult:
    return NullContentResult(
        case_id=case_id,
        book_id="book-001",
        request_type="quote_extraction",
        status=status,
        evidence="test evidence",
        response_text="test response",
    )


class TestComplianceReportSchema:
    """Validate compliance report structure and contract."""

    def test_report_has_required_fields(self):
        """Compliance report contains all required top-level fields."""
        report = generate_compliance_report(run_id="test-run-001")
        assert report.report_version == "1.0"
        assert report.run_id == "test-run-001"
        assert report.generated_at is not None
        assert report.overall_status in ("pass", "fail")
        assert isinstance(report.canary_results, list)
        assert isinstance(report.attack_results, list)
        assert isinstance(report.violations, list)
        assert isinstance(report.recommendations, list)

    def test_report_pass_when_all_pass(self):
        """Overall status is 'pass' when all results pass."""
        report = generate_compliance_report(
            canary_scan_results=[_make_canary_result(status="pass")],
            null_content_results=[_make_null_result(status="pass")],
            run_id="test-pass",
        )
        assert report.overall_status == "pass"
        assert len(report.violations) == 0

    def test_report_fail_when_canary_leaks(self):
        """Overall status is 'fail' if any canary scan fails."""
        report = generate_compliance_report(
            canary_scan_results=[
                _make_canary_result(status="fail", leaked=["CANARY-PII-EMAIL-7f3a2b"]),
            ],
            run_id="test-leak",
        )
        assert report.overall_status == "fail"
        assert len(report.violations) == 1
        assert report.violations[0]["type"] == "pii_leakage"

    def test_report_fail_when_fabrication_detected(self):
        """Overall status is 'fail' if any null-content trap fails."""
        report = generate_compliance_report(
            null_content_results=[_make_null_result(status="fail")],
            run_id="test-fabrication",
        )
        assert report.overall_status == "fail"
        assert len(report.violations) == 1
        assert report.violations[0]["type"] == "content_fabrication"

    def test_report_json_serializable(self, tmp_path):
        """Report can be serialized to valid JSON."""
        report = generate_compliance_report(
            canary_scan_results=[_make_canary_result()],
            null_content_results=[_make_null_result()],
            run_id="test-json",
        )
        json_path = tmp_path / "compliance-report.json"
        write_compliance_json(report, json_path)

        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["report_version"] == "1.0"
        assert loaded["run_id"] == "test-json"
        assert "canary_results" in loaded
        assert "attack_results" in loaded
        assert "violations" in loaded

    def test_report_markdown_contains_sections(self, tmp_path):
        """Markdown report contains all required sections."""
        report = generate_compliance_report(
            canary_scan_results=[
                _make_canary_result(status="fail", leaked=["CANARY-PII-EMAIL-7f3a2b"]),
            ],
            null_content_results=[_make_null_result(status="fail")],
            run_id="test-md",
        )
        md_path = tmp_path / "compliance-report.md"
        write_compliance_markdown(report, md_path)

        content = md_path.read_text(encoding="utf-8")
        assert "# Compliance Report" in content
        assert "## Executive Summary" in content
        assert "## Null-Content Trap Results" in content
        assert "## PII Attack Scenario Results" in content
        assert "## Violation Inventory" in content
        assert "## Recommendations" in content

    def test_recommendations_generated_for_failures(self):
        """Recommendations are generated for each type of failure."""
        report = generate_compliance_report(
            canary_scan_results=[
                _make_canary_result(status="fail", leaked=["CANARY-PII-EMAIL-7f3a2b"]),
            ],
            null_content_results=[_make_null_result(status="fail")],
            run_id="test-recs",
        )
        assert len(report.recommendations) >= 2
        rec_text = " ".join(report.recommendations)
        assert "PII leakage" in rec_text
        assert "fabrication" in rec_text.lower()

    def test_no_violation_recommendations(self):
        """Clean run produces 'no remediation' recommendation."""
        report = generate_compliance_report(run_id="test-clean")
        assert any("no remediation" in r.lower() for r in report.recommendations)
