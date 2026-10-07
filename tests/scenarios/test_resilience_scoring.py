"""Tests for the ResilienceEvaluator and scoring logic."""

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from resilience_evaluator import (
    ResilienceEvaluator,
    ResilienceMetrics,
    ChaosReport,
    build_chaos_report,
    WEIGHT_RECOVERY,
    WEIGHT_BUDGET,
    WEIGHT_DEGRADATION,
    WEIGHT_STATE_INTEGRITY,
)


@pytest.fixture
def evaluator():
    return ResilienceEvaluator()


class TestResilienceScoring:
    """Verify composite resilience scoring."""

    def test_perfect_recovery_high_score(self, evaluator):
        """Scenario passes under faults → score near 1.0."""
        metrics = evaluator.evaluate_scenario(
            scenario_id="test-1",
            test_status="passed",
            fault_profile="a2a_timeout_on_send",
            chaos_log=[{"fault": "timeout"}],
            max_budget=3,
            retry_attempts=1,
            forensic_status="pass",
        )
        assert metrics.resilience_score == 1.0
        assert metrics.recovery_success is True
        assert metrics.retry_budget_respected is True

    def test_budget_violation_penalizes_score(self, evaluator):
        """Retries exceed budget → score reduced by WEIGHT_BUDGET."""
        metrics = evaluator.evaluate_scenario(
            scenario_id="test-2",
            test_status="passed",
            fault_profile="registry_intermittent",
            chaos_log=[{"fault": "outage"}],
            max_budget=2,
            retry_attempts=5,
            forensic_status="pass",
        )
        expected = WEIGHT_RECOVERY + WEIGHT_DEGRADATION + WEIGHT_STATE_INTEGRITY
        assert abs(metrics.resilience_score - round(expected, 4)) < 0.001
        assert metrics.retry_budget_respected is False

    def test_state_integrity_failure_penalizes_score(self, evaluator):
        """Forensic fail → score reduced by WEIGHT_STATE_INTEGRITY."""
        metrics = evaluator.evaluate_scenario(
            scenario_id="test-3",
            test_status="passed",
            fault_profile="catalog_500_on_search",
            chaos_log=[{"fault": "500"}],
            max_budget=3,
            retry_attempts=1,
            forensic_status="fail",
        )
        expected = WEIGHT_RECOVERY + WEIGHT_BUDGET + WEIGHT_DEGRADATION
        assert abs(metrics.resilience_score - round(expected, 4)) < 0.001
        assert metrics.state_integrity_preserved is False

    def test_no_degradation_notice_penalizes_score(self, evaluator):
        """No faults injected (empty chaos_log) → degradation not triggered."""
        metrics = evaluator.evaluate_scenario(
            scenario_id="test-4",
            test_status="passed",
            fault_profile="none",
            chaos_log=[],
            max_budget=3,
            retry_attempts=0,
            forensic_status="pass",
        )
        expected = WEIGHT_RECOVERY + WEIGHT_BUDGET + WEIGHT_STATE_INTEGRITY
        assert abs(metrics.resilience_score - round(expected, 4)) < 0.001
        assert metrics.degraded_mode_used is False

    def test_aggregate_summary_structure(self, evaluator):
        """Summary has required keys."""
        m1 = evaluator.evaluate_scenario(
            scenario_id="s1", test_status="passed", fault_profile="p1",
            chaos_log=[{"f": 1}], max_budget=5, retry_attempts=1, forensic_status="pass",
        )
        m2 = evaluator.evaluate_scenario(
            scenario_id="s2", test_status="failed", fault_profile="p2",
            chaos_log=[{"f": 1}], max_budget=5, retry_attempts=3, forensic_status="pass",
        )
        summary = evaluator.aggregate_summary([m1, m2])

        required_keys = {
            "total_scenarios",
            "avg_resilience_score",
            "recovery_rate",
            "budget_compliance_rate",
            "state_integrity_rate",
        }
        assert required_keys <= set(summary.keys())
        assert summary["total_scenarios"] == 2

    def test_resilience_metrics_to_dict(self, evaluator):
        """All fields should be serializable via to_dict."""
        metrics = evaluator.evaluate_scenario(
            scenario_id="s1", test_status="passed", fault_profile="p1",
            chaos_log=[{"f": 1}], max_budget=5, retry_attempts=1, forensic_status="pass",
        )
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert d["scenario_id"] == "s1"
        assert d["resilience_score"] == 1.0


class TestChaosReportGeneration:
    """Verify chaos report building."""

    def test_build_chaos_report(self, evaluator):
        """build_chaos_report produces a valid ChaosReport."""
        m1 = evaluator.evaluate_scenario(
            scenario_id="s1", test_status="passed", fault_profile="p1",
            chaos_log=[{"f": 1}], max_budget=5, retry_attempts=1, forensic_status="pass",
        )
        report = build_chaos_report(
            run_id="test-run",
            fault_profiles=[{"profile_id": "p1"}],
            metrics=[m1],
            evaluator=evaluator,
        )
        assert report.run_id == "test-run"
        assert report.report_version == "1.3"
        assert len(report.scenario_results) == 1
        assert len(report.resilience_failures) == 0
