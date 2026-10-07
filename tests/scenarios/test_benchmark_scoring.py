"""Validation tests for benchmark scoring/report schema."""

from __future__ import annotations

import json
import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_run import load_manifest, parse_junit  # noqa: E402
from shared.eval.trace_writer import TraceWriter  # noqa: E402
from shared.eval.trace_schemas import TraceEventType  # noqa: E402


def test_parse_junit_emits_required_advanced_metric_fields(tmp_path):
    """Scoring output includes per-scenario v1 metric contract fields."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """
<testsuites>
  <testsuite name="pytest" tests="2" failures="1" errors="0" skipped="0">
    <testcase classname="tests.scenarios.test_tier1_catalog.TestTier1CatalogScenarios" name="test_tier1_find_book_by_author" time="0.01" />
    <testcase classname="tests.scenarios.test_tier2_circulation.TestTier2CirculationScenarios" name="test_tier2_checkout_updates_state" time="0.02">
      <failure message="assertion failed">status transition mismatch</failure>
    </testcase>
  </testsuite>
</testsuites>
        """.strip(),
        encoding="utf-8",
    )

    manifest_path = Path(__file__).parent / "scenario_manifest.json"
    manifest = load_manifest(manifest_path)

    report = parse_junit(junit_path=junit, manifest_entries=manifest)
    assert "summary" in report
    assert "scenarios" in report

    first = report["scenarios"][0]
    required = {
        "tier",
        "completion",
        "step_accuracy",
        "policy_compliance",
        "hallucinations",
        "tool_calls_total",
        "tool_calls_correct",
        "taxonomy",
    }
    assert required.issubset(set(first.keys()))

    summary = report["summary"]
    assert "completion" in summary
    assert "step_accuracy" in summary
    assert "policy_compliance" in summary
    assert "hallucinations" in summary
    assert "tool_calls_total" in summary
    assert "tool_calls_correct" in summary


def test_manifest_hint_drives_failure_taxonomy(tmp_path):
    """Manifest taxonomy hint should classify failures deterministically."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        """
<testsuites>
  <testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="tests.scenarios.test_tier3_ill_a2a.TestTier3ILLA2AScenarios" name="test_tier3_cross_library_happy_path" time="0.10">
      <failure message="boom">unexpected failure text</failure>
    </testcase>
  </testsuite>
</testsuites>
        """.strip(),
        encoding="utf-8",
    )

    manifest_path = Path(__file__).parent / "scenario_manifest.json"
    manifest = load_manifest(manifest_path)

    report = parse_junit(junit_path=junit, manifest_entries=manifest)
    scenario = report["scenarios"][0]
    assert scenario["scenario_id"] == "tier3_ill_cross_library_happy_path"
    assert scenario["taxonomy"] == "state_drift"


def test_report_contains_schema_version_and_trace_summary(tmp_path):
    """v1.1 report schema includes schema_version and trace_summary."""
    # Build a minimal report with trace writer to validate contract.
    trace_path = tmp_path / "trace.jsonl"
    writer = TraceWriter(trace_path, run_id="test-run-001")
    writer.emit(TraceEventType.BENCHMARK_RUN_START, "test")
    writer.emit(TraceEventType.BENCHMARK_RUN_END, "test")

    summary = writer.summary().model_dump(mode="json")

    report = {
        "schema_version": "1.1",
        "trace_summary": summary,
        "forensic_assertions": [],
    }

    assert report["schema_version"] == "1.1"
    assert report["trace_summary"]["run_id"] == "test-run-001"
    assert report["trace_summary"]["total_events"] == 2
    assert "benchmark_run_start" in report["trace_summary"]["event_type_counts"]
    assert isinstance(report["trace_summary"]["first_event_at"], str)
    assert isinstance(report["trace_summary"]["last_event_at"], str)
    assert isinstance(report["forensic_assertions"], list)


def test_report_schema_v1_1_includes_forensic_assertions():
    """v1.1 report schema requires forensic_assertions with valid structure."""
    sample_assertion = {
        "assertion_id": "inventory_conservation_v1",
        "status": "pass",
        "severity": "critical",
        "sql": "SELECT COUNT(*) FROM book_instances",
        "result": {"total": 41},
        "evidence": "Conservation law holds: 41 == 41",
    }

    report = {
        "schema_version": "1.1",
        "forensic_assertions": [sample_assertion],
    }

    for assertion in report["forensic_assertions"]:
        required = {"assertion_id", "status", "severity", "sql", "result", "evidence"}
        assert required.issubset(set(assertion.keys()))
        assert assertion["status"] in {"pass", "fail"}
