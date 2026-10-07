"""BenchmarkSessionExecutor — runs open-ended benchmark interactions against /chat.

Sends generated :class:`BenchmarkInteraction` objects to the live ``/chat``
endpoint, performs lightweight validation (tool engagement, coherence,
hallucination heuristic), and emits trace events for the frontend.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from agents.benchmark_config import (
    BenchmarkConfig,
    BenchmarkInteraction,
    InteractionResult,
)
from shared.eval.trace_schemas import TraceEventType
from shared.eval.trace_writer import TraceWriter

logger = logging.getLogger(__name__)

_SERVICE_TOKEN_HEADER = "x-service-token"
_DEFAULT_TOKEN = "dev-token-ai-librarian"

# Keywords indicating an error/traceback rather than a real response
_ERROR_MARKERS = ["traceback", "internal server error", "exception", "error processing"]

# Refusal keywords for edge-case detection
_REFUSAL_MARKERS = [
    "cannot",
    "blocked",
    "not allowed",
    "unable to",
    "account is blocked",
    "exceeds",
    "limit reached",
    "over the limit",
    "sorry",
]

# Domain keywords for coherence check
_DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "catalog": ["book", "title", "author", "isbn", "search", "found", "stratum", "genre"],
    "circulation": [
        "checkout", "checked out", "return", "hold", "fine", "renew",
        "patron", "account", "borrow", "due",
    ],
    "ill": [
        "inter-library", "ill", "loan", "partner", "request",
        "library", "borrow",
    ],
}


@dataclass
class BenchmarkAggregateMetrics:
    """Running aggregate metrics for a benchmark session."""

    total_interactions: int = 0
    completed: int = 0
    errored: int = 0
    timed_out: int = 0
    tool_engaged_count: int = 0
    hallucination_count: int = 0
    appropriate_refusal_count: int = 0
    total_response_time_ms: float = 0.0
    domain_breakdown: dict[str, dict[str, int]] = field(default_factory=dict)


class BenchmarkSessionExecutor:
    """Executes benchmark interactions against the live ``/chat`` endpoint."""

    def __init__(
        self,
        config: BenchmarkConfig,
        trace_writer: TraceWriter,
        chat_base_url: str = "http://localhost:8000",
        timeout_per_interaction: float = 60.0,
        known_book_titles: list[str] | None = None,
        known_authors: list[str] | None = None,
    ) -> None:
        self._config = config
        self._trace = trace_writer
        self._chat_url = chat_base_url.rstrip("/")
        self._timeout = timeout_per_interaction
        self._token = os.getenv("SERVICE_AUTH_TOKEN", _DEFAULT_TOKEN)
        self._metrics = BenchmarkAggregateMetrics()
        self._results: list[InteractionResult] = []
        self._session_cache: dict[str, str] = {}
        self._known_titles = set(
            t.lower() for t in (known_book_titles or [])
        )
        self._known_authors = set(
            a.lower() for a in (known_authors or [])
        )

    async def execute(
        self, interactions: list[BenchmarkInteraction]
    ) -> tuple[list[InteractionResult], BenchmarkAggregateMetrics]:
        """Execute all interactions, respecting time_budget_seconds."""
        start_time = time.monotonic()
        budget = self._config.time_budget_seconds

        for interaction in interactions:
            elapsed = time.monotonic() - start_time
            remaining = budget - elapsed
            if remaining < 0:
                logger.info(
                    "Time budget exhausted at %.1fs (%d/%d done)",
                    elapsed,
                    len(self._results),
                    len(interactions),
                )
                break

            self._metrics.total_interactions += 1
            result = await self._execute_interaction(interaction)
            self._results.append(result)
            self._update_metrics(result)

        return self._results, self._metrics

    async def _execute_interaction(
        self, interaction: BenchmarkInteraction
    ) -> InteractionResult:
        """Execute a single interaction against ``/chat``."""
        result = InteractionResult(
            interaction_id=interaction.interaction_id,
            sequence_id=interaction.sequence_id,
            patron_id=interaction.patron_id,
            interaction_type=interaction.interaction_type.value,
            expected_domain=interaction.expected_domain,
            complexity_tier=interaction.complexity_tier,
            message_sent=interaction.message,
            is_edge_case=interaction.is_edge_case,
        )

        # Emit start trace
        self._trace.emit(
            TraceEventType.BENCHMARK_INTERACTION_START,
            source="benchmark_executor",
            payload={
                "interaction_id": interaction.interaction_id,
                "interaction_type": interaction.interaction_type.value,
                "patron_id": interaction.patron_id,
                "expected_domain": interaction.expected_domain,
                "sequence_id": interaction.sequence_id,
                "is_edge_case": interaction.is_edge_case,
            },
        )

        trace_line_before = self._count_trace_lines()
        step_start = time.monotonic()

        try:
            response_text, session_id = await self._send_chat_message(
                interaction
            )
            result.agent_response = response_text

            # Cache session for sequence reuse
            if interaction.sequence_id and session_id:
                self._session_cache[interaction.sequence_id] = session_id

        except httpx.TimeoutException:
            result.error = "Timeout"
            result.status = "timeout"
            result.duration_ms = (time.monotonic() - step_start) * 1000
            self._emit_end(interaction, result)
            return result
        except Exception as exc:
            result.error = str(exc)[:500]
            result.status = "error"
            result.duration_ms = (time.monotonic() - step_start) * 1000
            self._emit_end(interaction, result)
            return result

        result.duration_ms = (time.monotonic() - step_start) * 1000

        # Extract tool calls from trace
        tool_calls = self._extract_tool_calls(trace_line_before)
        result.tool_calls_observed = tool_calls
        result.tool_engaged = len(tool_calls) > 0

        # Lightweight validation
        result.coherence_score = self._compute_coherence(
            response_text, interaction.expected_domain
        )
        result.hallucination_detected = self._detect_hallucination(
            response_text
        )
        result.appropriate_refusal = (
            interaction.is_edge_case
            and self._detect_refusal(response_text)
        )

        self._emit_end(interaction, result)
        return result

    async def _send_chat_message(
        self, interaction: BenchmarkInteraction
    ) -> tuple[str, str]:
        """POST to ``/chat`` and return ``(response_text, session_id)``."""
        body: dict[str, Any] = {
            "message": interaction.message,
            "active_patron": {
                "id": interaction.patron_id,
                "name": interaction.patron_name,
                "role": "patron",
            },
        }

        # Reuse session for sequences
        if interaction.sequence_id:
            cached = self._session_cache.get(interaction.sequence_id)
            if cached:
                body["session_id"] = cached

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._chat_url}/chat",
                json=body,
            )

        if resp.status_code != 200:
            raise RuntimeError(
                f"Chat returned {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        return data.get("response", ""), data.get("session_id", "")

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_coherence(response: str, domain: str) -> float:
        """Compute a simple 0-1 coherence score."""
        if not response or len(response.strip()) < 20:
            return 0.0

        lower = response.lower()

        # Check for error markers
        for marker in _ERROR_MARKERS:
            if marker in lower:
                return 0.1

        # Check for domain keywords
        keywords = _DOMAIN_KEYWORDS.get(domain, [])
        if not keywords:
            return 0.5

        matches = sum(1 for kw in keywords if kw in lower)
        keyword_score = min(matches / max(len(keywords) * 0.3, 1), 1.0)

        # Length factor (longer responses generally more coherent, up to a point)
        length_score = min(len(response) / 200, 1.0)

        return round(0.5 * keyword_score + 0.5 * length_score, 2)

    def _detect_hallucination(self, response: str) -> bool:
        """Heuristic: check if response mentions unknown book titles.

        Only flags if the response appears to cite a specific title
        (using quotes or title-case patterns) that isn't in seed data.
        This is a coarse heuristic — false positives are acceptable.
        """
        if not self._known_titles or not response:
            return False

        lower = response.lower()

        # Look for quoted strings that might be book titles
        import re

        quoted = re.findall(r"['\"]([^'\"]{5,80})['\"]", response)
        for candidate in quoted:
            candidate_lower = candidate.lower()
            # Skip if it matches a known title
            if candidate_lower in self._known_titles:
                continue
            # Skip common non-title quoted phrases
            if any(
                skip in candidate_lower
                for skip in [
                    "patron", "account", "library", "check", "hold",
                    "fine", "return", "sorry", "please", "thank",
                ]
            ):
                continue
            # If it looks like a book title (starts with capital), flag it
            if candidate[0].isupper():
                return True

        return False

    @staticmethod
    def _detect_refusal(response: str) -> bool:
        """Check if the response contains refusal language."""
        if not response:
            return False
        lower = response.lower()
        return any(marker in lower for marker in _REFUSAL_MARKERS)

    # ------------------------------------------------------------------
    # Trace helpers
    # ------------------------------------------------------------------

    def _count_trace_lines(self) -> int:
        if not self._trace or not self._trace.output_path.exists():
            return 0
        return len(self._trace.output_path.read_text().splitlines())

    def _extract_tool_calls(self, lines_before: int) -> list[str]:
        if not self._trace or not self._trace.output_path.exists():
            return []
        all_lines = self._trace.output_path.read_text().splitlines()
        new_lines = all_lines[lines_before:]
        names: list[str] = []
        for line in new_lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("event_type") == "tool_call":
                    name = event.get("payload", {}).get("tool_name", "")
                    if name:
                        names.append(name)
            except (json.JSONDecodeError, KeyError):
                continue
        return names

    def _emit_end(
        self, interaction: BenchmarkInteraction, result: InteractionResult
    ) -> None:
        self._trace.emit(
            TraceEventType.BENCHMARK_INTERACTION_END,
            source="benchmark_executor",
            payload={
                "interaction_id": result.interaction_id,
                "status": result.status,
                "duration_ms": result.duration_ms,
                "tool_engaged": result.tool_engaged,
                "tool_calls_observed": result.tool_calls_observed,
                "coherence_score": result.coherence_score,
                "hallucination_detected": result.hallucination_detected,
                "appropriate_refusal": result.appropriate_refusal,
                "error": result.error,
            },
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _update_metrics(self, result: InteractionResult) -> None:
        domain = result.expected_domain
        if domain not in self._metrics.domain_breakdown:
            self._metrics.domain_breakdown[domain] = {
                "total": 0,
                "completed": 0,
                "errored": 0,
            }
        self._metrics.domain_breakdown[domain]["total"] += 1

        if result.status == "completed":
            self._metrics.completed += 1
            self._metrics.domain_breakdown[domain]["completed"] += 1
            self._metrics.total_response_time_ms += result.duration_ms
            if result.tool_engaged:
                self._metrics.tool_engaged_count += 1
            if result.hallucination_detected:
                self._metrics.hallucination_count += 1
            if result.appropriate_refusal:
                self._metrics.appropriate_refusal_count += 1
        elif result.status == "timeout":
            self._metrics.timed_out += 1
            self._metrics.domain_breakdown[domain]["errored"] += 1
        else:
            self._metrics.errored += 1
            self._metrics.domain_breakdown[domain]["errored"] += 1
