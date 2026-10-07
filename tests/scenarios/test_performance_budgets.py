"""Performance budget tests.

Validates that performance budget documentation exists, the perf_smoke script
is functional, and budget thresholds are enforced for local alpha readiness.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs" / "development"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestPerformanceBudgetDocumentation:
    """Verify performance budget documentation exists and is complete."""

    def test_budget_doc_exists(self):
        """PERFORMANCE_BUDGETS.md is present."""
        doc = DOCS_DIR / "PERFORMANCE_BUDGETS.md"
        assert doc.exists(), f"Missing {doc}"

    def test_budget_doc_defines_thresholds(self):
        """Budget doc contains required threshold values."""
        doc = DOCS_DIR / "PERFORMANCE_BUDGETS.md"
        content = doc.read_text(encoding="utf-8")
        for keyword in ["2000", "5000", "10000", "Health Endpoint"]:
            assert keyword in content, f"Budget doc missing threshold: {keyword}"


class TestPerfSmokeScript:
    """Verify perf_smoke.py is importable and well-formed."""

    def test_perf_smoke_script_exists(self):
        """scripts/perf_smoke.py is present."""
        assert (SCRIPTS_DIR / "perf_smoke.py").exists()

    def test_perf_smoke_imports_cleanly(self):
        """Module imports and exposes PerformanceSmokeRunner."""
        from perf_smoke import PerformanceSmokeRunner

        assert PerformanceSmokeRunner is not None

    def test_perf_smoke_runner_has_required_methods(self):
        """PerformanceSmokeRunner has run_all and write_report."""
        from perf_smoke import PerformanceSmokeRunner

        runner = PerformanceSmokeRunner(project_root=PROJECT_ROOT)
        assert callable(getattr(runner, "run_all", None))
        assert callable(getattr(runner, "write_report", None))


class TestPerfSmokeExecution:
    """Run perf smoke and validate output."""

    def test_perf_smoke_produces_valid_report(self, tmp_path: Path):
        """Perf smoke run produces a valid JSON report with required schema."""
        from perf_smoke import PerformanceSmokeRunner

        runner = PerformanceSmokeRunner(project_root=PROJECT_ROOT)
        runner.run_all()
        report_path = tmp_path / "perf-smoke-report.json"
        runner.write_report(report_path)

        assert report_path.exists()
        report = json.loads(report_path.read_text(encoding="utf-8"))

        for field in ["schema_version", "budgets", "results", "violations", "summary"]:
            assert field in report, f"Report missing field: {field}"

        assert isinstance(report["results"], list)
        assert isinstance(report["violations"], list)
        assert "total_checks" in report["summary"]

    def test_perf_smoke_health_checks_cover_all_services(self, tmp_path: Path):
        """Health check results include all 4 backend services."""
        from perf_smoke import PerformanceSmokeRunner

        runner = PerformanceSmokeRunner(project_root=PROJECT_ROOT)
        results, _ = runner.run_all()

        services_checked = {
            r["service"] for r in results if r.get("endpoint") == "/health"
        }
        expected = {"catalog", "circulation", "ill", "registry"}
        assert expected.issubset(services_checked), (
            f"Missing services: {expected - services_checked}"
        )

    def test_perf_smoke_report_budget_values(self, tmp_path: Path):
        """Report budgets match expected constants."""
        from perf_smoke import (
            HEALTH_ENDPOINT_BUDGET_MS,
            REPORT_GENERATION_BUDGET_MS,
            PERF_SMOKE_TOTAL_BUDGET_MS,
            PerformanceSmokeRunner,
        )

        runner = PerformanceSmokeRunner(project_root=PROJECT_ROOT)
        runner.run_all()
        report_path = tmp_path / "perf-smoke-report.json"
        runner.write_report(report_path)

        report = json.loads(report_path.read_text(encoding="utf-8"))
        budgets = report["budgets"]

        assert budgets["health_endpoint_ms"] == HEALTH_ENDPOINT_BUDGET_MS
        assert budgets["report_generation_ms"] == REPORT_GENERATION_BUDGET_MS
        assert budgets["total_smoke_ms"] == PERF_SMOKE_TOTAL_BUDGET_MS
