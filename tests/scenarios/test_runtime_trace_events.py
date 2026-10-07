"""Runtime trace helper tests for tool-call live stream events."""

from __future__ import annotations

import json

from shared.eval.runtime_trace import (
    begin_tool_call,
    end_tool_call,
)


def test_runtime_tool_call_emits_start_and_end_events(monkeypatch, tmp_path):
    """Runtime trace helper writes tool start/end events to trace file."""
    output = tmp_path / "runtime-trace.jsonl"
    monkeypatch.setenv("BENCHMARK_TRACE_ENABLED", "1")
    monkeypatch.setenv("BENCHMARK_TRACE_PATH", str(output))
    monkeypatch.setenv("BENCHMARK_TRACE_ID", "trace-runtime-test")
    monkeypatch.setenv("BENCHMARK_RUN_ID", "run-runtime-test")
    monkeypatch.setenv("BENCHMARK_ACTIVE_SCENARIO_ID", "scenario-alpha")

    call_id, started = begin_tool_call(
        source="agents.tools.catalog",
        tool_name="search_books",
        input_payload={"query": "Baron Probost"},
    )
    end_tool_call(
        source="agents.tools.catalog",
        tool_name="search_books",
        call_id=call_id,
        started=started,
        success=True,
        output_payload={"total": 1},
    )

    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    second = json.loads(lines[1])

    assert first["event_type"] == "tool_call"
    assert first["scenario_id"] == "scenario-alpha"
    assert first["payload"]["phase"] == "start"
    assert first["payload"]["tool"] == "search_books"

    assert second["event_type"] == "tool_call"
    assert second["payload"]["phase"] == "end"
    assert second["payload"]["status"] == "passed"
    assert isinstance(second["payload"]["duration_ms"], float)


def test_runtime_trace_is_noop_without_env(monkeypatch, tmp_path):
    """Runtime tool call helper should not write when tracing is disabled."""
    output = tmp_path / "runtime-trace.jsonl"
    monkeypatch.delenv("BENCHMARK_TRACE_ENABLED", raising=False)
    monkeypatch.setenv("BENCHMARK_TRACE_PATH", str(output))

    call_id, started = begin_tool_call(
        source="agents.tools.catalog",
        tool_name="search_books",
        input_payload={"query": "silent"},
    )
    end_tool_call(
        source="agents.tools.catalog",
        tool_name="search_books",
        call_id=call_id,
        started=started,
        success=True,
        output_payload={},
    )

    assert not output.exists()
