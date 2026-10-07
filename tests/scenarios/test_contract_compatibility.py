"""Contract compatibility tests for benchmark artifact schemas.

Validates that current code can consume golden fixture files and that
schema evolution follows the compatibility policy.
"""

import json
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_run import load_manifest  # noqa: E402


class TestReportCompatibility:
    """Verify benchmark report schema compatibility."""

    def test_v1_1_report_has_required_summary_fields(self):
        """Golden v1.1 report contains all required summary fields."""
        golden = json.loads(
            (FIXTURES_DIR / "benchmark-report-v1.1.json").read_text(encoding="utf-8")
        )
        assert "schema_version" in golden
        assert "summary" in golden

        summary = golden["summary"]
        required_summary = {
            "total", "passed", "failed", "skipped",
            "completion", "step_accuracy", "policy_compliance",
            "hallucinations", "tool_calls_total", "tool_calls_correct",
            "tool_precision",
        }
        assert required_summary.issubset(set(summary.keys())), (
            f"Missing fields: {required_summary - set(summary.keys())}"
        )
        assert "trace_summary" in golden
        assert "forensic_assertions" in golden

    def test_breaking_change_detected_missing_required_field(self):
        """Removing a required field is caught by field-set check."""
        golden = json.loads(
            (FIXTURES_DIR / "benchmark-report-v1.1.json").read_text(encoding="utf-8")
        )
        del golden["summary"]["completion"]

        required_summary = {
            "total", "passed", "failed", "skipped",
            "completion", "step_accuracy", "policy_compliance",
            "hallucinations", "tool_calls_total", "tool_calls_correct",
        }
        assert not required_summary.issubset(set(golden["summary"].keys()))

    def test_additive_change_passes_compatibility(self):
        """Adding an optional field does not break compatibility."""
        golden = json.loads(
            (FIXTURES_DIR / "benchmark-report-v1.1.json").read_text(encoding="utf-8")
        )
        golden["summary"]["new_metric_v2"] = 0.95

        required_summary = {
            "total", "passed", "failed", "skipped",
            "completion", "step_accuracy", "policy_compliance",
        }
        assert required_summary.issubset(set(golden["summary"].keys()))

    def test_current_report_schema_version_format(self):
        """Schema version string is a valid major.minor format."""
        golden = json.loads(
            (FIXTURES_DIR / "benchmark-report-v1.1.json").read_text(encoding="utf-8")
        )
        version = golden["schema_version"]
        parts = version.split(".")
        assert len(parts) == 2, f"Expected major.minor format, got {version}"
        assert all(p.isdigit() for p in parts), f"Non-numeric version parts: {version}"


class TestManifestCompatibility:
    """Verify scenario manifest schema compatibility."""

    def test_v1_4_manifest_loads_without_error(self):
        """Current manifest loader handles v1.4 golden fixture."""
        golden_path = FIXTURES_DIR / "scenario-manifest-v1.4.json"
        manifest = load_manifest(golden_path)
        assert len(manifest) == 1
        assert manifest[0].scenario_id == "golden_tier1"
        assert manifest[0].tier == 1


class TestRunIndexCompatibility:
    """Verify run index schema compatibility."""

    def test_v1_5_run_index_structure(self):
        """RunIndex Pydantic model validates v1.5 golden fixture."""
        from agents.benchmark_api_models import RunIndex

        golden = json.loads(
            (FIXTURES_DIR / "run-index-v1.5.json").read_text(encoding="utf-8")
        )
        index = RunIndex.model_validate(golden)
        assert index.schema_version == "1.5"
        assert len(index.runs) == 1
        assert index.runs[0].run_id == "golden-run-001"
        assert index.runs[0].status.value == "passed"
        assert index.runs[0].model_name == "gemini-3.0-flash"
        assert index.runs[0].model_family == "gemini"
        assert index.runs[0].scenario_ids == ["tier1_author_search"]
        assert index.runs[0].trigger_source == "assistant_card"
        assert index.runs[0].actor_patron_id == "patron-003"
