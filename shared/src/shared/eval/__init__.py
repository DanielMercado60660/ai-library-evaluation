"""Evaluation trace and forensic assertion contracts."""

from shared.eval.trace_schemas import (
    TraceEvent,
    TraceEventType,
    TraceSummary,
    ForensicSeverity,
    ForensicAssertionResult,
    ForensicAssertionReport,
)
from shared.eval.trace_writer import TraceWriter
from shared.eval.scenario_steps import (
    build_default_scenario_steps,
    derive_step_outcomes,
)
from shared.eval.runtime_trace import (
    runtime_trace_enabled,
    get_active_scenario_id,
    summarize_for_trace,
    begin_tool_call,
    end_tool_call,
    emit_runtime_event,
)
from shared.eval.eval_script_schemas import (
    StepAssertion,
    EvalStep,
    EvalScript,
    EvalScriptCatalog,
)

__all__ = [
    "TraceEvent",
    "TraceEventType",
    "TraceSummary",
    "ForensicSeverity",
    "ForensicAssertionResult",
    "ForensicAssertionReport",
    "TraceWriter",
    "build_default_scenario_steps",
    "derive_step_outcomes",
    "runtime_trace_enabled",
    "get_active_scenario_id",
    "summarize_for_trace",
    "begin_tool_call",
    "end_tool_call",
    "emit_runtime_event",
    "StepAssertion",
    "EvalStep",
    "EvalScript",
    "EvalScriptCatalog",
]
