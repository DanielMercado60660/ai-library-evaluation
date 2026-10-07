"""Unit tests for benchmark_report_builder."""

import pytest

from agents.benchmark_config import BenchmarkConfig, InteractionResult
from agents.benchmark_report_builder import (
    build_benchmark_markdown,
    build_benchmark_report,
)
from agents.benchmark_session_executor import BenchmarkAggregateMetrics


def _make_result(
    interaction_id: str = "bm-0001",
    domain: str = "catalog",
    status: str = "completed",
    tool_engaged: bool = True,
    hallucination: bool = False,
    duration_ms: float = 500.0,
) -> InteractionResult:
    return InteractionResult(
        interaction_id=interaction_id,
        patron_id="patron-001",
        interaction_type="catalog_search",
        expected_domain=domain,
        complexity_tier="simple",
        message_sent="Find me a book",
        agent_response="Here is a book.",
        tool_engaged=tool_engaged,
        tool_calls_observed=["search_books"] if tool_engaged else [],
        coherence_score=0.7,
        hallucination_detected=hallucination,
        duration_ms=duration_ms,
        status=status,
    )


def _make_metrics(
    total: int = 10,
    completed: int = 8,
    errored: int = 2,
    tool_engaged: int = 6,
    hallucinations: int = 1,
    total_time_ms: float = 4000.0,
) -> BenchmarkAggregateMetrics:
    return BenchmarkAggregateMetrics(
        total_interactions=total,
        completed=completed,
        errored=errored,
        tool_engaged_count=tool_engaged,
        hallucination_count=hallucinations,
        total_response_time_ms=total_time_ms,
        domain_breakdown={
            "catalog": {"total": 3, "completed": 3, "errored": 0},
            "circulation": {"total": 5, "completed": 4, "errored": 1},
            "ill": {"total": 2, "completed": 1, "errored": 1},
        },
    )


class TestBuildBenchmarkReport:
    """Test build_benchmark_report produces v1.5-compatible report."""

    def test_basic_structure(self):
        results = [_make_result()]
        metrics = _make_metrics(total=1, completed=1, errored=0)
        config = BenchmarkConfig(interaction_count=1)

        report = build_benchmark_report(
            run_id="run-test",
            results=results,
            metrics=metrics,
            config=config,
        )

        assert report["schema_version"] == "1.5"
        assert report["run_mode"] == "benchmark"
        assert report["run_id"] == "run-test"
        assert "summary" in report
        assert "scenarios" in report
        assert "benchmark_details" in report
        assert "forensic_assertions" in report

    def test_summary_has_composite_score_fields(self):
        """Ensure all fields required by composite_score() are present."""
        metrics = _make_metrics()
        results = [_make_result(interaction_id=f"bm-{i:04d}") for i in range(10)]
        config = BenchmarkConfig(interaction_count=10)

        report = build_benchmark_report(
            run_id="run-test",
            results=results,
            metrics=metrics,
            config=config,
        )

        summary = report["summary"]
        # These are the exact fields composite_score() reads
        assert "completion_rate_percent" in summary
        assert "policy_compliance_percent" in summary
        assert "tool_precision_percent" in summary
        assert "hallucinations" in summary
        assert "total" in summary

    def test_completion_rate_calculation(self):
        metrics = _make_metrics(total=10, completed=8)
        report = build_benchmark_report(
            run_id="run-test",
            results=[],
            metrics=metrics,
            config=BenchmarkConfig(),
        )
        assert report["summary"]["completion_rate_percent"] == 80.0

    def test_zero_total_no_division_error(self):
        metrics = BenchmarkAggregateMetrics()
        report = build_benchmark_report(
            run_id="run-test",
            results=[],
            metrics=metrics,
            config=BenchmarkConfig(),
        )
        assert report["summary"]["completion_rate_percent"] == 0.0
        assert report["summary"]["tool_precision_percent"] == 0.0
        assert report["summary"]["policy_compliance_percent"] == 0.0

    def test_domain_scenarios_grouping(self):
        results = [
            _make_result(interaction_id="bm-001", domain="catalog"),
            _make_result(interaction_id="bm-002", domain="catalog"),
            _make_result(interaction_id="bm-003", domain="circulation"),
            _make_result(interaction_id="bm-004", domain="ill"),
        ]
        metrics = _make_metrics(total=4, completed=4, errored=0)

        report = build_benchmark_report(
            run_id="run-test",
            results=results,
            metrics=metrics,
            config=BenchmarkConfig(),
        )

        scenario_ids = [s["scenario_id"] for s in report["scenarios"]]
        assert "benchmark_catalog" in scenario_ids
        assert "benchmark_circulation" in scenario_ids
        assert "benchmark_ill" in scenario_ids

    def test_scenario_tiers(self):
        results = [
            _make_result(interaction_id="bm-001", domain="catalog"),
            _make_result(interaction_id="bm-002", domain="circulation"),
            _make_result(interaction_id="bm-003", domain="ill"),
        ]
        metrics = _make_metrics(total=3, completed=3, errored=0)

        report = build_benchmark_report(
            run_id="run-test",
            results=results,
            metrics=metrics,
            config=BenchmarkConfig(),
        )

        tiers = {s["scenario_id"]: s["tier"] for s in report["scenarios"]}
        assert tiers["benchmark_catalog"] == 1
        assert tiers["benchmark_circulation"] == 2
        assert tiers["benchmark_ill"] == 3

    def test_benchmark_details_present(self):
        metrics = _make_metrics()
        config = BenchmarkConfig(interaction_count=10)
        results = [_make_result()]

        report = build_benchmark_report(
            run_id="run-test",
            results=results,
            metrics=metrics,
            config=config,
            wall_clock_seconds=42.5,
        )

        details = report["benchmark_details"]
        assert details["total_interactions"] == metrics.total_interactions
        assert details["completed"] == metrics.completed
        assert details["errored"] == metrics.errored
        assert details["wall_clock_seconds"] == 42.5
        assert "config" in details
        assert "interactions" in details
        assert len(details["interactions"]) == 1

    def test_hallucination_count_in_summary(self):
        metrics = _make_metrics(hallucinations=3)
        report = build_benchmark_report(
            run_id="run-test",
            results=[],
            metrics=metrics,
            config=BenchmarkConfig(),
        )
        assert report["summary"]["hallucinations"] == 3


class TestBuildBenchmarkMarkdown:
    """Test build_benchmark_markdown generates readable markdown."""

    def test_markdown_output(self):
        metrics = _make_metrics()
        config = BenchmarkConfig(interaction_count=10)
        report = build_benchmark_report(
            run_id="run-md",
            results=[_make_result()],
            metrics=metrics,
            config=config,
        )

        md = build_benchmark_markdown(report)

        assert "# Benchmark Run Summary" in md
        assert "run-md" in md
        assert "benchmark" in md
        assert "Total interactions" in md

    def test_empty_report_markdown(self):
        metrics = BenchmarkAggregateMetrics()
        config = BenchmarkConfig()
        report = build_benchmark_report(
            run_id="run-empty",
            results=[],
            metrics=metrics,
            config=config,
        )

        md = build_benchmark_markdown(report)
        assert "# Benchmark Run Summary" in md
