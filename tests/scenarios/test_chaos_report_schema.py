"""Tests for chaos/resilience report schema structure."""

import json
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from resilience_evaluator import (
    ChaosReport,
    ResilienceEvaluator,
    ResilienceMetrics,
    build_chaos_report,
    write_chaos_json,
    write_chaos_markdown,
)


@pytest.fixture
def sample_report():
    """Build a sample ChaosReport for schema testing."""
    ev = ResilienceEvaluator()
    m1 = ev.evaluate_scenario(
        scenario_id="chaos_a2a_timeout",
        test_status="passed",
        fault_profile="a2a_timeout_on_send",
        chaos_log=[{"fault": "timeout", "call_index": 0}],
        max_budget=3,
        retry_attempts=1,
        forensic_status="pass",
    )
    m2 = ev.evaluate_scenario(
        scenario_id="chaos_catalog_500",
        test_status="failed",
        fault_profile="catalog_500_on_search",
        chaos_log=[{"fault": "http_500", "call_index": 0}],
        max_budget=3,
        retry_attempts=2,
        forensic_status="pass",
    )
    return build_chaos_report(
        run_id="schema-test-run",
        fault_profiles=[
            {"profile_id": "a2a_timeout_on_send"},
            {"profile_id": "catalog_500_on_search"},
        ],
        metrics=[m1, m2],
        evaluator=ev,
    )


class TestChaosReportSchema:
    """Validate report structure."""

    def test_chaos_report_required_fields(self, sample_report):
        """Report has all top-level required fields."""
        d = asdict(sample_report)
        required = {
            "report_version",
            "run_id",
            "generated_at",
            "fault_profiles",
            "scenario_results",
            "resilience_failures",
            "state_integrity_checks",
            "aggregate",
        }
        assert required <= set(d.keys())
        assert d["report_version"] == "1.3"

    def test_chaos_report_md_sections(self, sample_report):
        """Markdown output has executive summary and fault matrix."""
        with tempfile.TemporaryDirectory() as tmp:
            md_path = Path(tmp) / "chaos-report.md"
            write_chaos_markdown(sample_report, md_path)
            text = md_path.read_text(encoding="utf-8")

        assert "## Executive Summary" in text
        assert "## Fault Matrix" in text
        assert "chaos_a2a_timeout" in text

    def test_chaos_report_json_roundtrip(self, sample_report):
        """JSON write/read preserves structure."""
        with tempfile.TemporaryDirectory() as tmp:
            json_path = Path(tmp) / "chaos-report.json"
            write_chaos_json(sample_report, json_path)
            loaded = json.loads(json_path.read_text(encoding="utf-8"))

        assert loaded["report_version"] == "1.3"
        assert len(loaded["scenario_results"]) == 2

    def test_resilience_failures_have_evidence(self, sample_report):
        """Each failure entry includes evidence."""
        for failure in sample_report.resilience_failures:
            assert "evidence" in failure
            assert "scenario_id" in failure
