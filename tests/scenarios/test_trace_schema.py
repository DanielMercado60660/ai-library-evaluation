"""Tests for trace event schema and trace writer."""

from __future__ import annotations

import json
from datetime import datetime, UTC

import pytest

from shared.eval.trace_schemas import (
    TraceEvent,
    TraceEventType,
    TraceSummary,
)
from shared.eval.trace_writer import TraceWriter


class TestTraceEventSchema:
    """Validate trace event model contract."""

    def test_trace_event_validates_required_fields(self):
        event = TraceEvent(
            trace_id="trace-abc",
            run_id="run-123",
            event_type=TraceEventType.BENCHMARK_RUN_START,
            source="benchmark_runner",
        )
        assert event.trace_id == "trace-abc"
        assert event.run_id == "run-123"
        assert event.event_type == TraceEventType.BENCHMARK_RUN_START.value
        assert event.source == "benchmark_runner"
        assert event.scenario_id is None
        assert event.payload == {}
        assert isinstance(event.timestamp, datetime)

    def test_trace_event_rejects_invalid_event_type(self):
        with pytest.raises(Exception):
            TraceEvent(
                trace_id="trace-abc",
                run_id="run-123",
                event_type="not_a_real_event",
                source="test",
            )

    def test_trace_event_accepts_optional_fields(self):
        event = TraceEvent(
            trace_id="trace-abc",
            run_id="run-123",
            event_type=TraceEventType.SCENARIO_END,
            source="test",
            scenario_id="tier1_search",
            payload={"status": "passed", "tier": 1},
        )
        assert event.scenario_id == "tier1_search"
        assert event.payload["status"] == "passed"

    def test_trace_event_serializes_timestamps(self):
        event = TraceEvent(
            trace_id="trace-abc",
            run_id="run-123",
            event_type=TraceEventType.TOOL_CALL,
            source="adk_adapter",
        )
        dumped = event.model_dump(mode="json")
        assert isinstance(dumped["timestamp"], str)
        # Should be ISO format parseable
        datetime.fromisoformat(dumped["timestamp"])


class TestTraceWriter:
    """Validate JSONL trace writer."""

    def test_trace_writer_emits_jsonl(self, tmp_path):
        output = tmp_path / "trace.jsonl"
        writer = TraceWriter(output)

        writer.emit(TraceEventType.BENCHMARK_RUN_START, "runner")
        writer.emit(TraceEventType.SCENARIO_START, "runner", scenario_id="s1")
        writer.emit(TraceEventType.SCENARIO_END, "runner", scenario_id="s1")

        lines = output.read_text().strip().split("\n")
        assert len(lines) == 3

        for line in lines:
            parsed = json.loads(line)
            assert "trace_id" in parsed
            assert "run_id" in parsed
            assert "event_type" in parsed
            assert "source" in parsed
            assert "timestamp" in parsed

    def test_trace_writer_summary_counts(self, tmp_path):
        output = tmp_path / "trace.jsonl"
        writer = TraceWriter(output)

        writer.emit(TraceEventType.BENCHMARK_RUN_START, "runner")
        writer.emit(TraceEventType.SCENARIO_START, "runner", scenario_id="s1")
        writer.emit(TraceEventType.TOOL_CALL, "adk", scenario_id="s1", payload={"tool": "search"})
        writer.emit(TraceEventType.TOOL_CALL, "adk", scenario_id="s1", payload={"tool": "detail"})
        writer.emit(TraceEventType.SCENARIO_END, "runner", scenario_id="s1")
        writer.emit(TraceEventType.BENCHMARK_RUN_END, "runner")

        summary = writer.summary()
        assert summary.total_events == 6
        assert summary.event_type_counts["tool_call"] == 2
        assert summary.event_type_counts["benchmark_run_start"] == 1
        assert summary.trace_id == writer.trace_id
        assert summary.run_id == writer.run_id
        assert summary.first_event_at <= summary.last_event_at

    def test_trace_writer_consistent_ids(self, tmp_path):
        output = tmp_path / "trace.jsonl"
        writer = TraceWriter(output, run_id="fixed-run-id")

        writer.emit(TraceEventType.BENCHMARK_RUN_START, "runner")
        writer.emit(TraceEventType.BENCHMARK_RUN_END, "runner")

        lines = output.read_text().strip().split("\n")
        for line in lines:
            parsed = json.loads(line)
            assert parsed["run_id"] == "fixed-run-id"
            assert parsed["trace_id"] == writer.trace_id

    def test_trace_writer_summary_serializable(self, tmp_path):
        output = tmp_path / "trace.jsonl"
        writer = TraceWriter(output)

        writer.emit(TraceEventType.BENCHMARK_RUN_START, "runner")

        summary = writer.summary()
        dumped = summary.model_dump(mode="json")
        # Should be JSON-serializable
        json.dumps(dumped)
        assert isinstance(dumped["first_event_at"], str)
        assert isinstance(dumped["last_event_at"], str)

    def test_trace_writer_summary_includes_external_runtime_events(self, tmp_path):
        output = tmp_path / "trace.jsonl"
        writer = TraceWriter(output, run_id="run-ext")
        writer.emit(TraceEventType.BENCHMARK_RUN_START, "runner")

        external = TraceEvent(
            trace_id=writer.trace_id,
            run_id=writer.run_id,
            scenario_id="scenario-ext",
            event_type=TraceEventType.TOOL_CALL,
            source="agents.tools.catalog",
            payload={"tool": "search_books", "phase": "start", "status": "running"},
        )
        with output.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(external.model_dump(mode="json")) + "\n")

        summary = writer.summary()
        assert summary.total_events == 2
        assert summary.event_type_counts["tool_call"] == 1
