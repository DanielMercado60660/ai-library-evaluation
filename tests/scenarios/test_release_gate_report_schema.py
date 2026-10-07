"""Release gate report schema tests.

Validates the release gate script structure, report schema, and runner behavior
for v2.0 RC promotion readiness.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestReleaseGateScript:
    """Verify release gate script exists and is well-formed."""

    def test_release_gate_script_exists(self):
        """scripts/release_gate_v2_0_rc.py is present."""
        assert (SCRIPTS_DIR / "release_gate_v2_0_rc.py").exists()

    def test_release_gate_imports_cleanly(self):
        """Module imports and exposes ReleaseGateRunner."""
        from release_gate_v2_0_rc import ReleaseGateRunner

        assert ReleaseGateRunner is not None

    def test_release_gate_runner_has_required_methods(self):
        """ReleaseGateRunner has run_all_gates, build_report, write_json_report, write_markdown_report."""
        from release_gate_v2_0_rc import ReleaseGateRunner

        runner = ReleaseGateRunner()
        for method_name in [
            "run_all_gates",
            "build_report",
            "write_json_report",
            "write_markdown_report",
        ]:
            assert callable(getattr(runner, method_name, None)), (
                f"Missing method: {method_name}"
            )


class TestReleaseGateReportSchema:
    """Verify report schema structure and status logic."""

    def _make_runner_with_gates(self, statuses: list[str]):
        """Create a runner with synthetic gate results."""
        from release_gate_v2_0_rc import GateResult, ReleaseGateRunner

        runner = ReleaseGateRunner()
        for i, status in enumerate(statuses):
            runner.gates.append(
                GateResult(
                    name=f"gate_{i}",
                    status=status,
                    duration_ms=10.0 * (i + 1),
                    evidence=f"evidence for gate_{i}",
                    command=f"check_{i}",
                    exit_code=0 if status == "pass" else 1,
                )
            )
        return runner

    def test_report_has_required_top_level_fields(self):
        """Report contains schema_version, target_version, generated_at, overall_status, gates, summary."""
        runner = self._make_runner_with_gates(["pass"])
        report = runner.build_report()

        for field in [
            "schema_version",
            "target_version",
            "generated_at",
            "overall_status",
            "gates",
            "summary",
        ]:
            assert field in report, f"Report missing field: {field}"

    def test_gate_result_has_required_fields(self):
        """Each gate in the report has name, status, duration_ms, evidence."""
        runner = self._make_runner_with_gates(["pass", "fail"])
        report = runner.build_report()

        for gate in report["gates"]:
            for field in ["name", "status", "duration_ms", "evidence"]:
                assert field in gate, f"Gate missing field: {field}"

    def test_overall_status_promotable_when_all_pass(self):
        """All pass → 'promotable'."""
        runner = self._make_runner_with_gates(["pass", "pass", "pass"])
        assert runner.compute_overall_status() == "promotable"

    def test_overall_status_blocked_when_any_fail(self):
        """Any fail → 'blocked'."""
        runner = self._make_runner_with_gates(["pass", "fail", "pass"])
        assert runner.compute_overall_status() == "blocked"

    def test_summary_counts_match_gates(self):
        """Summary passed/failed/skipped counts match gate list."""
        runner = self._make_runner_with_gates(["pass", "fail", "skip", "pass"])
        report = runner.build_report()
        summary = report["summary"]

        assert summary["total"] == 4
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["skipped"] == 1


class TestReleaseGateReportGeneration:
    """Test report file generation."""

    def test_json_report_round_trip(self, tmp_path: Path):
        """Write → load → validate JSON report."""
        from release_gate_v2_0_rc import GateResult, ReleaseGateRunner

        runner = ReleaseGateRunner()
        runner.gates.append(
            GateResult(name="test_gate", status="pass", duration_ms=5.0, evidence="ok")
        )

        report_path = tmp_path / "report.json"
        runner.write_json_report(report_path)

        assert report_path.exists()
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert loaded["schema_version"] == "1.0"
        assert loaded["target_version"] == "v2.0-rc"
        assert len(loaded["gates"]) == 1

    def test_markdown_report_includes_table(self, tmp_path: Path):
        """Markdown report includes a gate results table."""
        from release_gate_v2_0_rc import GateResult, ReleaseGateRunner

        runner = ReleaseGateRunner()
        runner.gates.append(
            GateResult(name="test_gate", status="pass", duration_ms=5.0, evidence="ok")
        )

        report_path = tmp_path / "report.md"
        runner.write_markdown_report(report_path)

        content = report_path.read_text(encoding="utf-8")
        assert "| Gate |" in content or "| gate |" in content.lower()
        assert "test_gate" in content

    def test_markdown_report_shows_promotion_status(self, tmp_path: Path):
        """Markdown report has Promotion Readiness section."""
        from release_gate_v2_0_rc import GateResult, ReleaseGateRunner

        runner = ReleaseGateRunner()
        runner.gates.append(
            GateResult(name="test_gate", status="pass", duration_ms=5.0, evidence="ok")
        )

        report_path = tmp_path / "report.md"
        runner.write_markdown_report(report_path)

        content = report_path.read_text(encoding="utf-8")
        assert "Promotion Readiness" in content


class TestReleaseGateRunner:
    """Test runner behavior and flags."""

    def test_dry_run_mode_does_not_execute_gates(self):
        """Dry run lists gates without adding any results."""
        from release_gate_v2_0_rc import ReleaseGateRunner

        runner = ReleaseGateRunner()
        result = runner.run_all_gates(dry_run=True)
        assert result == []
        assert len(runner.gates) == 0

    def test_skip_frontend_flag_skips_frontend_build(self):
        """Frontend build gate has status='skip' when skip_frontend=True."""
        from release_gate_v2_0_rc import ReleaseGateRunner

        runner = ReleaseGateRunner()
        gate = runner.run_frontend_build(skip=True)
        assert gate.status == "skip"
        assert "skip" in gate.evidence.lower()

    def test_all_gate_methods_exist(self):
        """All 7 run_* gate methods are present."""
        from release_gate_v2_0_rc import ReleaseGateRunner

        runner = ReleaseGateRunner()
        expected_methods = [
            "run_adr_governance",
            "run_dependency_boundaries",
            "run_resilience_policy",
            "run_performance_smoke",
            "run_recovery_drill",
            "run_test_count_verification",
            "run_frontend_build",
        ]
        for method_name in expected_methods:
            assert callable(getattr(runner, method_name, None)), (
                f"Missing gate method: {method_name}"
            )
