"""EvalScriptExecutor — replays prescripted eval scripts against live /chat.

The executor sends patron messages to ``POST /chat``, checks tool-call
expectations, validates response content, and runs state assertions against
backend services. Each step emits EVAL_STEP_START / EVAL_STEP_END trace
events so the frontend can render live progress.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import httpx

from shared.eval.eval_script_schemas import EvalScript, EvalStep, StepAssertion
from shared.eval.trace_schemas import TraceEventType
from shared.eval.trace_writer import TraceWriter

logger = logging.getLogger(__name__)

_SERVICE_TOKEN_HEADER = "x-service-token"
_DEFAULT_TOKEN = "dev-token-ai-librarian"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class AssertionResult:
    """Result of a single assertion check."""

    assertion_type: str  # "tool_call", "content_contains", "content_not_contains", "state"
    passed: bool
    details: str = ""


@dataclass
class EvalStepResult:
    """Result of executing one eval step."""

    step_id: str
    order: int
    patron_message: str
    agent_response: str = ""
    tool_calls_observed: list[str] = field(default_factory=list)
    assertions: list[AssertionResult] = field(default_factory=list)
    passed: bool = True
    duration_ms: float = 0.0
    error: str | None = None


@dataclass
class EvalScenarioResult:
    """Aggregate result for one scenario."""

    scenario_id: str
    steps: list[EvalStepResult] = field(default_factory=list)
    passed: bool = True
    total_assertions: int = 0
    passed_assertions: int = 0
    duration_ms: float = 0.0


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class EvalScriptExecutor:
    """Replays eval scripts against the live ``/chat`` endpoint."""

    def __init__(
        self,
        chat_base_url: str = "http://localhost:8000",
        trace_writer: TraceWriter | None = None,
        service_urls: dict[str, str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        self._chat_url = chat_base_url.rstrip("/")
        self._trace = trace_writer
        self._service_urls = service_urls or {
            "catalog": os.getenv("CATALOG_URL", "http://localhost:8001"),
            "circulation": os.getenv("CIRCULATION_URL", "http://localhost:8002"),
            "ill": os.getenv("RECOMMENDATION_URL", "http://localhost:8003"),
            "registry": os.getenv("AUTH_URL", "http://localhost:8004"),
        }
        self._timeout = timeout
        self._token = os.getenv("SERVICE_AUTH_TOKEN", _DEFAULT_TOKEN)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_scenario(
        self,
        scenario_id: str,
        script: EvalScript,
        run_id: str = "",
    ) -> EvalScenarioResult:
        """Execute all steps in an eval script and return results."""
        result = EvalScenarioResult(scenario_id=scenario_id)
        scenario_start = time.monotonic()
        session_id: str | None = None

        for step in script.steps:
            step_result, session_id = await self._execute_step(
                step=step,
                session_id=session_id,
                patron_id=script.patron_id,
                patron_name=script.patron_name,
                patron_role=script.patron_role,
                scenario_id=scenario_id,
            )
            result.steps.append(step_result)
            result.total_assertions += len(step_result.assertions)
            result.passed_assertions += sum(
                1 for a in step_result.assertions if a.passed
            )
            if not step_result.passed:
                result.passed = False

        result.duration_ms = (time.monotonic() - scenario_start) * 1000
        return result

    # ------------------------------------------------------------------
    # Step execution
    # ------------------------------------------------------------------

    async def _execute_step(
        self,
        step: EvalStep,
        session_id: str | None,
        patron_id: str,
        patron_name: str,
        patron_role: str,
        scenario_id: str,
    ) -> tuple[EvalStepResult, str | None]:
        """Execute a single eval step."""
        step_result = EvalStepResult(
            step_id=step.step_id,
            order=step.order,
            patron_message=step.patron_message,
        )

        # Emit EVAL_STEP_START
        if self._trace:
            self._trace.emit(
                TraceEventType.EVAL_STEP_START,
                source="eval_executor",
                scenario_id=scenario_id,
                payload={
                    "step_id": step.step_id,
                    "order": step.order,
                    "patron_message": step.patron_message,
                },
            )

        step_start = time.monotonic()
        trace_line_before = self._count_trace_lines()

        try:
            response_text, session_id = await self._send_chat_message(
                message=step.patron_message,
                session_id=session_id,
                patron_id=patron_id,
                patron_name=patron_name,
                patron_role=patron_role,
                timeout=step.timeout_seconds,
            )
            step_result.agent_response = response_text
        except Exception as exc:
            step_result.error = str(exc)
            step_result.passed = False
            step_result.duration_ms = (time.monotonic() - step_start) * 1000
            self._emit_step_end(step, step_result, scenario_id)
            return step_result, session_id

        step_result.duration_ms = (time.monotonic() - step_start) * 1000

        # Check tool calls from trace
        if step.expected_tool_calls:
            observed = self._extract_tool_calls_from_trace(trace_line_before)
            step_result.tool_calls_observed = observed
            tool_assertions = self._check_tool_calls(
                step.expected_tool_calls, observed
            )
            step_result.assertions.extend(tool_assertions)

        # Check response content
        content_assertions = self._check_response_content(
            response_text,
            step.response_must_contain,
            step.response_must_not_contain,
        )
        step_result.assertions.extend(content_assertions)

        # Check state assertions
        if step.state_assertions:
            state_assertions = await self._check_state_assertions(
                step.state_assertions
            )
            step_result.assertions.extend(state_assertions)

        # Overall step pass
        if any(not a.passed for a in step_result.assertions):
            step_result.passed = False

        self._emit_step_end(step, step_result, scenario_id)
        return step_result, session_id

    # ------------------------------------------------------------------
    # Chat interaction
    # ------------------------------------------------------------------

    async def _send_chat_message(
        self,
        message: str,
        session_id: str | None,
        patron_id: str,
        patron_name: str,
        patron_role: str,
        timeout: float = 30.0,
    ) -> tuple[str, str]:
        """POST to /chat and return (response_text, session_id)."""
        body: dict[str, Any] = {
            "message": message,
            "active_patron": {
                "id": patron_id,
                "name": patron_name,
                "role": patron_role,
            },
        }
        if session_id:
            body["session_id"] = session_id

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self._chat_url}/chat",
                json=body,
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Chat returned {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        return data.get("response", ""), data.get("session_id", session_id or "")

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def _check_tool_calls(
        self,
        expected: list[str],
        observed: list[str],
    ) -> list[AssertionResult]:
        """Check that expected tool calls were observed (order-independent)."""
        results: list[AssertionResult] = []
        observed_set = set(observed)
        for tool_name in expected:
            matched = tool_name in observed_set
            results.append(AssertionResult(
                assertion_type="tool_call",
                passed=matched,
                details=f"Expected tool '{tool_name}' {'found' if matched else 'NOT found'} in {observed}",
            ))
        return results

    @staticmethod
    def _check_response_content(
        response: str,
        must_contain: list[str],
        must_not_contain: list[str],
    ) -> list[AssertionResult]:
        """Check response text for required/forbidden substrings."""
        results: list[AssertionResult] = []
        lower_resp = response.lower()

        for substring in must_contain:
            found = substring.lower() in lower_resp
            results.append(AssertionResult(
                assertion_type="content_contains",
                passed=found,
                details=f"'{substring}' {'found' if found else 'NOT found'} in response",
            ))

        for substring in must_not_contain:
            found = substring.lower() in lower_resp
            results.append(AssertionResult(
                assertion_type="content_not_contains",
                passed=not found,
                details=f"'{substring}' {'unexpectedly found' if found else 'correctly absent'} in response",
            ))

        return results

    async def _check_state_assertions(
        self,
        assertions: list[StepAssertion],
    ) -> list[AssertionResult]:
        """Check backend service state via HTTP GET."""
        results: list[AssertionResult] = []

        async with httpx.AsyncClient(timeout=10.0) as client:
            for assertion in assertions:
                base_url = self._service_urls.get(assertion.service, "")
                if not base_url:
                    results.append(AssertionResult(
                        assertion_type="state",
                        passed=False,
                        details=f"Unknown service '{assertion.service}'",
                    ))
                    continue

                url = f"{base_url.rstrip('/')}{assertion.endpoint}"
                try:
                    resp = await client.get(
                        url,
                        headers={_SERVICE_TOKEN_HEADER: self._token},
                    )
                    if resp.status_code != 200:
                        results.append(AssertionResult(
                            assertion_type="state",
                            passed=False,
                            details=f"GET {url} returned {resp.status_code}",
                        ))
                        continue

                    data = resp.json()
                    actual = self._resolve_field_path(data, assertion.field_path)
                    passed = self._values_match(actual, assertion.expected_value)
                    results.append(AssertionResult(
                        assertion_type="state",
                        passed=passed,
                        details=(
                            f"{assertion.field_path}={actual!r} "
                            f"{'==' if passed else '!='} "
                            f"expected {assertion.expected_value!r}"
                        ),
                    ))
                except Exception as exc:
                    results.append(AssertionResult(
                        assertion_type="state",
                        passed=False,
                        details=f"Error checking {url}: {exc}",
                    ))

        return results

    # ------------------------------------------------------------------
    # Trace parsing helpers
    # ------------------------------------------------------------------

    def _count_trace_lines(self) -> int:
        """Count current number of lines in the trace file."""
        if not self._trace or not self._trace.output_path.exists():
            return 0
        return len(self._trace.output_path.read_text().splitlines())

    def _extract_tool_calls_from_trace(self, lines_before: int) -> list[str]:
        """Extract tool call names from trace lines added since ``lines_before``."""
        if not self._trace or not self._trace.output_path.exists():
            return []

        all_lines = self._trace.output_path.read_text().splitlines()
        new_lines = all_lines[lines_before:]
        tool_names: list[str] = []

        for line in new_lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("event_type") == "tool_call":
                    name = event.get("payload", {}).get("tool_name", "")
                    if name:
                        tool_names.append(name)
            except (json.JSONDecodeError, KeyError):
                continue

        return tool_names

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_field_path(data: Any, path: str) -> Any:
        """Resolve a dot-separated field path into a JSON value.

        Supports integer keys for list indexing (e.g. ``items.0.status``).
        """
        current = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    @staticmethod
    def _values_match(actual: Any, expected: Any) -> bool:
        """Compare actual and expected with basic type coercion."""
        if actual == expected:
            return True
        # Coerce numeric types
        try:
            if float(actual) == float(expected):
                return True
        except (TypeError, ValueError):
            pass
        # String comparison
        return str(actual) == str(expected)

    def _emit_step_end(
        self,
        step: EvalStep,
        result: EvalStepResult,
        scenario_id: str,
    ) -> None:
        """Emit EVAL_STEP_END trace event."""
        if not self._trace:
            return

        assertion_summaries = [
            {
                "type": a.assertion_type,
                "passed": a.passed,
                "details": a.details,
            }
            for a in result.assertions
        ]

        self._trace.emit(
            TraceEventType.EVAL_STEP_END,
            source="eval_executor",
            scenario_id=scenario_id,
            payload={
                "step_id": result.step_id,
                "order": result.order,
                "passed": result.passed,
                "duration_ms": result.duration_ms,
                "agent_response_length": len(result.agent_response),
                "tool_calls_observed": result.tool_calls_observed,
                "assertions": assertion_summaries,
                "error": result.error,
            },
        )
