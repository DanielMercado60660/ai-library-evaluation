"""Unit tests for _execute_benchmark_run in BenchmarkOrchestrator."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.benchmark_api_models import RunCreateRequest, RunMetadata, RunStatus
from agents.benchmark_config import BenchmarkConfig, InteractionResult
from agents.benchmark_orchestrator import BenchmarkOrchestrator
from agents.benchmark_session_executor import BenchmarkAggregateMetrics


@pytest.fixture
def artifacts_dir(tmp_path) -> Path:
    return tmp_path / "artifacts"


@pytest.fixture
def orchestrator(artifacts_dir) -> BenchmarkOrchestrator:
    return BenchmarkOrchestrator(artifacts_dir)


def _make_request(
    run_mode: str = "benchmark",
    suite: str = "benchmark",
    benchmark_config: dict | None = None,
) -> RunCreateRequest:
    return RunCreateRequest(
        suite=suite,
        run_mode=run_mode,
        model_name="gemini-3.0-flash",
        benchmark_config=benchmark_config or {"interaction_count": 5, "time_budget_seconds": 60},
        trigger_source="test",
    )


class TestCreateBenchmarkRun:
    """Test orchestrator creates and routes benchmark runs correctly."""

    def test_create_run_returns_metadata(self, orchestrator):
        request = _make_request()
        metadata = orchestrator.create_run(request)

        assert metadata.run_id
        assert metadata.status == RunStatus.QUEUED
        assert metadata.suite == "benchmark"
        assert metadata.model_name == "gemini-3.0-flash"

    def test_run_listed_after_creation(self, orchestrator):
        request = _make_request()
        metadata = orchestrator.create_run(request)

        runs = orchestrator.list_runs()
        assert any(r.run_id == metadata.run_id for r in runs)

    def test_run_get_returns_created_run(self, orchestrator):
        request = _make_request()
        metadata = orchestrator.create_run(request)

        retrieved = orchestrator.get_run(metadata.run_id)
        assert retrieved is not None
        assert retrieved.run_id == metadata.run_id


class TestExecuteBenchmarkRun:
    """Test _execute_benchmark_run with mocked components."""

    @pytest.mark.asyncio
    async def test_benchmark_run_writes_report(self, orchestrator):
        request = _make_request()
        metadata = orchestrator.create_run(request)

        mock_results = [
            InteractionResult(
                interaction_id="bm-0001",
                patron_id="patron-001",
                interaction_type="catalog_search",
                expected_domain="catalog",
                complexity_tier="simple",
                message_sent="Find a book",
                agent_response="Here is a book.",
                tool_engaged=True,
                tool_calls_observed=["search_books"],
                coherence_score=0.8,
                status="completed",
                duration_ms=100.0,
            ),
        ]
        mock_metrics = BenchmarkAggregateMetrics(
            total_interactions=1,
            completed=1,
            tool_engaged_count=1,
            total_response_time_ms=100.0,
            domain_breakdown={"catalog": {"total": 1, "completed": 1, "errored": 0}},
        )

        with (
            patch("agents.eval_seeder.EvalDatabaseSeeder") as mock_seeder_cls,
            patch("agents.patron_request_generator.PatronRequestGenerator") as mock_gen_cls,
            patch("agents.benchmark_session_executor.BenchmarkSessionExecutor") as mock_exec_cls,
        ):
            mock_seeder = AsyncMock()
            mock_seeder_cls.return_value = mock_seeder

            mock_gen = MagicMock()
            mock_gen.generate.return_value = []
            mock_gen._books = [{"title": "Test Book"}]
            mock_gen._authors = [{"name": "Test Author"}]
            mock_gen_cls.return_value = mock_gen

            mock_executor = AsyncMock()
            mock_executor.execute.return_value = (mock_results, mock_metrics)
            mock_exec_cls.return_value = mock_executor

            await orchestrator._execute_benchmark_run(metadata.run_id, request)

        # Verify report was written
        updated = orchestrator.get_run(metadata.run_id)
        assert updated is not None
        assert updated.status in {RunStatus.PASSED, RunStatus.FAILED}
        assert updated.report_path is not None

        report_path = Path(updated.report_path)
        assert report_path.exists()

        report = json.loads(report_path.read_text())
        assert report["schema_version"] == "1.5"
        assert report["run_mode"] == "benchmark"
        assert report["summary"]["total"] == 1

    @pytest.mark.asyncio
    async def test_benchmark_run_skips_seed_when_disabled(self, orchestrator):
        config = {"interaction_count": 5, "seed_before_run": False}
        request = _make_request(benchmark_config=config)
        metadata = orchestrator.create_run(request)

        with (
            patch("agents.eval_seeder.EvalDatabaseSeeder") as mock_seeder_cls,
            patch("agents.patron_request_generator.PatronRequestGenerator") as mock_gen_cls,
            patch("agents.benchmark_session_executor.BenchmarkSessionExecutor") as mock_exec_cls,
        ):
            mock_gen = MagicMock()
            mock_gen.generate.return_value = []
            mock_gen._books = []
            mock_gen._authors = []
            mock_gen_cls.return_value = mock_gen

            mock_executor = AsyncMock()
            mock_executor.execute.return_value = ([], BenchmarkAggregateMetrics())
            mock_exec_cls.return_value = mock_executor

            await orchestrator._execute_benchmark_run(metadata.run_id, request)

        # Seeder class should not be instantiated when seed_before_run=False
        mock_seeder_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_benchmark_run_handles_errors_gracefully(self, orchestrator):
        request = _make_request()
        metadata = orchestrator.create_run(request)

        with (
            patch("agents.eval_seeder.EvalDatabaseSeeder") as mock_seeder_cls,
            patch("agents.patron_request_generator.PatronRequestGenerator") as mock_gen_cls,
        ):
            mock_seeder = AsyncMock()
            mock_seeder_cls.return_value = mock_seeder

            mock_gen_cls.side_effect = RuntimeError("Generator failed")

            await orchestrator._execute_benchmark_run(metadata.run_id, request)

        updated = orchestrator.get_run(metadata.run_id)
        assert updated is not None
        assert updated.status == RunStatus.FAILED
        assert updated.error_message is not None
