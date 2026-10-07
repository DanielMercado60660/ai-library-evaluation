"""Unit tests for eval report builder."""

import pytest

from agents.eval_executor import (
    AssertionResult,
    EvalScenarioResult,
    EvalStepResult,
)
from agents.eval_report import build_eval_report, build_eval_markdown


def _make_step(
    step_id: str = "step_1",
    order: int = 1,
    passed: bool = True,
    tool_calls: list[str] | None = None,
    assertions: list[AssertionResult] | None = None,
) -> EvalStepResult:
    return EvalStepResult(
        step_id=step_id,
        order=order,
        patron_message=f"Message for {step_id}",
        agent_response=f"Response for {step_id}",
        tool_calls_observed=tool_calls or [],
        assertions=assertions or [],
        passed=passed,
        duration_ms=100.0,
    )


def _make_scenario(
    scenario_id: str = "test_scenario",
    passed: bool = True,
    steps: list[EvalStepResult] | None = None,
) -> EvalScenarioResult:
    steps = steps or [_make_step()]
    total_assertions = sum(len(s.assertions) for s in steps)
    passed_assertions = sum(
        1 for s in steps for a in s.assertions if a.passed
    )
    return EvalScenarioResult(
        scenario_id=scenario_id,
        steps=steps,
        passed=passed,
        total_assertions=total_assertions,
        passed_assertions=passed_assertions,
        duration_ms=500.0,
    )


class TestBuildEvalReport:
    """Test build_eval_report produces v1.5-compatible report."""

    def test_basic_report_structure(self):
        result = _make_scenario()
        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[result],
            model_name="gemini-3.0-flash",
        )

        assert report["schema_version"] == "1.5"
        assert report["run_mode"] == "eval"
        assert report["run_id"] == "run-abc"
        assert report["model_name"] == "gemini-3.0-flash"
        assert "summary" in report
        assert "scenarios" in report
        assert "eval_details" in report
        assert "forensic_assertions" in report

    def test_summary_counts(self):
        passed = _make_scenario(scenario_id="s1", passed=True)
        failed = _make_scenario(scenario_id="s2", passed=False)
        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[passed, failed],
        )

        summary = report["summary"]
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_completion_rate(self):
        passing_step = _make_step(step_id="s1", order=1, passed=True)
        failing_step = _make_step(step_id="s2", order=2, passed=False)
        scenario = _make_scenario(
            steps=[passing_step, failing_step],
            passed=False,
        )

        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        scenario_entry = report["scenarios"][0]
        assert scenario_entry["completion"] == 0.5  # 1 of 2 steps passed

    def test_hallucination_count(self):
        assertions = [
            AssertionResult("content_not_contains", passed=False, details="found bad content"),
            AssertionResult("content_contains", passed=True, details="ok"),
        ]
        step = _make_step(assertions=assertions, passed=False)
        scenario = _make_scenario(steps=[step], passed=False)

        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        scenario_entry = report["scenarios"][0]
        assert scenario_entry["hallucinations"] == 1

    def test_tool_precision(self):
        assertions = [
            AssertionResult("tool_call", passed=True, details="search_books found"),
            AssertionResult("tool_call", passed=False, details="checkout_book NOT found"),
        ]
        step = _make_step(
            tool_calls=["search_books"],
            assertions=assertions,
            passed=False,
        )
        scenario = _make_scenario(steps=[step], passed=False)

        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        scenario_entry = report["scenarios"][0]
        assert scenario_entry["tool_precision"] == 0.5

    def test_eval_details_structure(self):
        assertions = [
            AssertionResult("content_contains", passed=True, details="found 'book'"),
        ]
        step = _make_step(step_id="step_1", assertions=assertions)
        scenario = _make_scenario(scenario_id="s1", steps=[step])

        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        assert "s1" in report["eval_details"]
        detail = report["eval_details"]["s1"]
        assert detail["scenario_id"] == "s1"
        assert detail["passed"] is True
        assert len(detail["steps"]) == 1

        step_detail = detail["steps"][0]
        assert step_detail["step_id"] == "step_1"
        assert step_detail["patron_message"] == "Message for step_1"
        assert step_detail["agent_response"] == "Response for step_1"
        assert len(step_detail["assertions"]) == 1
        assert step_detail["assertions"][0]["type"] == "content_contains"

    def test_empty_scenario_list(self):
        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[],
        )
        assert report["summary"]["total"] == 0
        assert report["summary"]["passed"] == 0
        assert report["summary"]["completion_rate"] == 0.0

    def test_policy_compliance(self):
        assertions = [
            AssertionResult("content_contains", passed=True, details="ok"),
            AssertionResult("content_contains", passed=False, details="missing"),
            AssertionResult("tool_call", passed=True, details="tool ok"),
        ]
        step = _make_step(
            tool_calls=["tool1"],
            assertions=assertions,
            passed=False,
        )
        scenario = _make_scenario(steps=[step], passed=False)

        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        scenario_entry = report["scenarios"][0]
        # Policy = non-tool assertions: 1 passed / 2 total = 0.5
        assert scenario_entry["policy_compliance"] == 0.5


class TestBuildEvalMarkdown:
    """Test build_eval_markdown generates readable markdown."""

    def test_markdown_output(self):
        scenario = _make_scenario(scenario_id="s1")
        report = build_eval_report(
            run_id="run-abc",
            scenario_results=[scenario],
        )

        md = build_eval_markdown(report)

        assert "# Eval Run Summary" in md
        assert "run-abc" in md
        assert "s1" in md
        assert "Total scenarios" in md

    def test_empty_report_markdown(self):
        report = build_eval_report(
            run_id="run-empty",
            scenario_results=[],
        )
        md = build_eval_markdown(report)
        assert "# Eval Run Summary" in md
        assert "0" in md
