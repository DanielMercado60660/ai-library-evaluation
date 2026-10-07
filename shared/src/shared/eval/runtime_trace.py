"""Runtime trace helpers for live benchmark tool-call observability."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from shared.eval.trace_schemas import TraceEvent, TraceEventType

TRACE_ENABLED_ENV = "BENCHMARK_TRACE_ENABLED"
TRACE_PATH_ENV = "BENCHMARK_TRACE_PATH"
TRACE_ID_ENV = "BENCHMARK_TRACE_ID"
RUN_ID_ENV = "BENCHMARK_RUN_ID"
ACTIVE_SCENARIO_ENV = "BENCHMARK_ACTIVE_SCENARIO_ID"

_WRITE_LOCK = threading.Lock()


def runtime_trace_enabled() -> bool:
    """Return True when runtime trace event emission is enabled."""
    enabled = os.getenv(TRACE_ENABLED_ENV, "").strip().lower()
    return enabled in {"1", "true", "yes", "on"} and bool(
        os.getenv(TRACE_PATH_ENV)
    )


def get_active_scenario_id() -> str | None:
    """Return the active scenario id injected by pytest hooks, if set."""
    value = os.getenv(ACTIVE_SCENARIO_ENV, "").strip()
    return value or None


def summarize_for_trace(
    value: Any,
    *,
    max_depth: int = 2,
    max_items: int = 6,
    max_string: int = 180,
) -> Any:
    """Build a compact JSON-safe summary suitable for trace payloads."""
    if max_depth <= 0:
        return _scalar_summary(value, max_string=max_string)

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        items = list(value.items())[:max_items]
        for key, item_value in items:
            out[str(key)] = summarize_for_trace(
                item_value,
                max_depth=max_depth - 1,
                max_items=max_items,
                max_string=max_string,
            )
        if len(value) > max_items:
            out["_truncated_keys"] = len(value) - max_items
        return out

    if isinstance(value, (list, tuple)):
        sample = [
            summarize_for_trace(
                item,
                max_depth=max_depth - 1,
                max_items=max_items,
                max_string=max_string,
            )
            for item in list(value)[:max_items]
        ]
        summary: dict[str, Any] = {"count": len(value), "sample": sample}
        if len(value) > max_items:
            summary["truncated_items"] = len(value) - max_items
        return summary

    return _scalar_summary(value, max_string=max_string)


def begin_tool_call(
    *,
    source: str,
    tool_name: str,
    input_payload: dict[str, Any] | None = None,
    scenario_id: str | None = None,
    parent_step_id: str = "tool_execution",
) -> tuple[str | None, float]:
    """Emit a tool_call start event and return (call_id, monotonic_start)."""
    started = time.perf_counter()
    if not runtime_trace_enabled():
        return None, started

    call_id = f"call-{uuid4().hex[:12]}"
    emit_runtime_event(
        TraceEventType.TOOL_CALL,
        source,
        scenario_id=scenario_id,
        payload={
            "call_id": call_id,
            "phase": "start",
            "status": "running",
            "tool": tool_name,
            "parent_step_id": parent_step_id,
            "input": summarize_for_trace(input_payload or {}),
        },
    )
    return call_id, started


def end_tool_call(
    *,
    source: str,
    tool_name: str,
    call_id: str | None,
    started: float,
    success: bool,
    output_payload: Any = None,
    error: str | None = None,
    scenario_id: str | None = None,
    parent_step_id: str = "tool_execution",
) -> None:
    """Emit a tool_call end event."""
    if not runtime_trace_enabled():
        return

    elapsed_ms = round((time.perf_counter() - started) * 1000.0, 2)
    payload: dict[str, Any] = {
        "call_id": call_id or f"call-{uuid4().hex[:12]}",
        "phase": "end",
        "status": "passed" if success else "failed",
        "tool": tool_name,
        "parent_step_id": parent_step_id,
        "duration_ms": elapsed_ms,
    }
    if success:
        payload["output"] = summarize_for_trace(output_payload)
    else:
        payload["error"] = (error or "unknown error")[:280]

    emit_runtime_event(
        TraceEventType.TOOL_CALL,
        source,
        scenario_id=scenario_id,
        payload=payload,
    )


def emit_runtime_event(
    event_type: TraceEventType,
    source: str,
    *,
    scenario_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TraceEvent | None:
    """Append a trace event to the configured benchmark trace file.

    This function is intentionally fail-safe: it never raises for trace
    emission failures, so benchmark business logic continues uninterrupted.
    """
    trace_path = os.getenv(TRACE_PATH_ENV, "").strip()
    if not trace_path:
        return None

    try:
        resolved_scenario_id = scenario_id or get_active_scenario_id()
        trace_event = TraceEvent(
            trace_id=os.getenv(TRACE_ID_ENV, "").strip() or f"trace-{uuid4().hex[:16]}",
            run_id=os.getenv(RUN_ID_ENV, "").strip() or f"run-{uuid4().hex[:16]}",
            scenario_id=resolved_scenario_id,
            event_type=event_type,
            source=source,
            payload=payload or {},
        )
        target = Path(trace_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(trace_event.model_dump(mode="json"))
        with _WRITE_LOCK:
            with target.open("a", encoding="utf-8") as handle:
                handle.write(f"{line}\n")
        return trace_event
    except Exception:
        return None


def _scalar_summary(value: Any, *, max_string: int) -> Any:
    """Summarize scalar/non-container values for trace payloads."""
    if isinstance(value, str):
        if len(value) <= max_string:
            return value
        return f"{value[:max_string]}..."

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    rendered = str(value)
    if len(rendered) <= max_string:
        return rendered
    return f"{rendered[:max_string]}..."
