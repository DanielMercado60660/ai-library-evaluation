"""Integration tests for deterministic ADK benchmark runner."""

import tempfile
from pathlib import Path

import pytest

from agents.benchmark_runner import BenchmarkRunner, DeterministicADKAdapter
from shared.eval.trace_writer import TraceWriter


MANIFEST_PATH = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "scenarios"
    / "scenario_manifest.json"
)


class TestBenchmarkRunner:
    """Validate ADK-integrated benchmark execution and scoring shape."""

    def test_load_manifest(self):
        runner = BenchmarkRunner(manifest_path=MANIFEST_PATH)
        definitions = runner.load_manifest()

        assert definitions
        assert any(item.tier == 3 for item in definitions)
        assert any(item.scenario_id == "tier3_ill_cross_library_happy_path" for item in definitions)

    @pytest.mark.asyncio
    async def test_run_tier_subset_returns_expected_metrics(self):
        runner = BenchmarkRunner(manifest_path=MANIFEST_PATH)
        result = await runner.run(min_tier=1, max_tier=3)

        assert result["total"] >= 3
        assert 0.0 <= result["completion"] <= 1.0
        assert 0.0 <= result["step_accuracy"] <= 1.0
        assert 0.0 <= result["policy_compliance"] <= 1.0
        assert result["tool_calls_total"] >= result["tool_calls_correct"]

        first = result["results"][0]
        required_fields = {
            "scenario_id",
            "tier",
            "completion",
            "step_accuracy",
            "policy_compliance",
            "hallucinations",
            "tool_calls_total",
            "tool_calls_correct",
            "taxonomy",
            "tool_trace",
        }
        assert required_fields.issubset(set(first.keys()))

    @pytest.mark.asyncio
    async def test_adapter_uses_adk_tool_mappings(self):
        adapter = DeterministicADKAdapter()
        runner = BenchmarkRunner(manifest_path=MANIFEST_PATH, adapter=adapter)

        result = await runner.run(min_tier=1, max_tier=1)
        assert result["results"]

        for scenario in result["results"]:
            assert scenario["tool_trace"]
            assert isinstance(scenario["tool_trace"], list)

    def test_trace_writer_uses_provided_run_id(self):
        """TraceWriter uses the explicit run_id when provided."""
        with tempfile.TemporaryDirectory() as tmp:
            tw = TraceWriter(Path(tmp) / "trace.jsonl", run_id="run-test1234")
            assert tw.run_id == "run-test1234"

    def test_trace_writer_auto_generates_run_id(self):
        """TraceWriter generates a run_id when none is provided."""
        with tempfile.TemporaryDirectory() as tmp:
            tw = TraceWriter(Path(tmp) / "trace.jsonl")
            assert tw.run_id.startswith("run-")
            assert len(tw.run_id) > 4
