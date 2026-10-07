"""Trace event and forensic assertion schemas for benchmark evaluation."""

from datetime import datetime, UTC
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class TraceEventType(str, Enum):
    """Supported trace event types for benchmark runs."""

    BENCHMARK_RUN_START = "benchmark_run_start"
    BENCHMARK_RUN_END = "benchmark_run_end"
    SCENARIO_START = "scenario_start"
    SCENARIO_STEP_START = "scenario_step_start"
    SCENARIO_STEP_END = "scenario_step_end"
    SCENARIO_END = "scenario_end"
    TOOL_CALL = "tool_call"
    ASSERTION_START = "assertion_start"
    ASSERTION_RESULT = "assertion_result"
    DB_SNAPSHOT = "db_snapshot"
    SAFETY_CHECK_START = "safety_check_start"
    SAFETY_CHECK_RESULT = "safety_check_result"
    CHAOS_FAULT_INJECTED = "chaos_fault_injected"
    CHAOS_RECOVERY_ATTEMPT = "chaos_recovery_attempt"
    RESILIENCE_SCORE_COMPUTED = "resilience_score_computed"
    EVAL_STEP_START = "eval_step_start"
    EVAL_STEP_END = "eval_step_end"
    EVAL_ASSERTION_RESULT = "eval_assertion_result"
    BENCHMARK_INTERACTION_START = "benchmark_interaction_start"
    BENCHMARK_INTERACTION_END = "benchmark_interaction_end"


class TraceEvent(BaseModel):
    """Single trace event emitted during a benchmark run."""

    model_config = ConfigDict(use_enum_values=True)

    trace_id: str
    run_id: str
    scenario_id: str | None = None
    event_type: TraceEventType
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class TraceSummary(BaseModel):
    """Aggregated summary of a benchmark trace."""

    trace_id: str
    run_id: str
    total_events: int
    event_type_counts: dict[str, int]
    first_event_at: datetime
    last_event_at: datetime
    trace_file: str


class ForensicSeverity(str, Enum):
    """Severity levels for forensic assertions."""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class ForensicAssertionResult(BaseModel):
    """Result of a single forensic SQL assertion."""

    model_config = ConfigDict(use_enum_values=True)

    assertion_id: str
    status: Literal["pass", "fail"]
    severity: ForensicSeverity
    sql: str
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: str


class ForensicAssertionReport(BaseModel):
    """Complete forensic assertion report for a benchmark run."""

    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    assertions: list[ForensicAssertionResult]
    summary: dict[str, int]
