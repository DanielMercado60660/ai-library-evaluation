"""Unit tests for BenchmarkSessionExecutor."""

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agents.benchmark_config import (
    BenchmarkConfig,
    BenchmarkInteraction,
    InteractionResult,
    InteractionType,
)
from agents.benchmark_session_executor import (
    BenchmarkAggregateMetrics,
    BenchmarkSessionExecutor,
)


def _make_interaction(
    interaction_id: str = "bm-0001",
    itype: InteractionType = InteractionType.CATALOG_SEARCH,
    patron_id: str = "patron-001",
    message: str = "Find me a book",
    sequence_id: str | None = None,
    is_edge_case: bool = False,
) -> BenchmarkInteraction:
    return BenchmarkInteraction(
        interaction_id=interaction_id,
        patron_id=patron_id,
        patron_name="Test Patron",
        patron_category="adult",
        message=message,
        interaction_type=itype,
        expected_domain="catalog",
        complexity_tier="simple",
        sequence_id=sequence_id,
        is_edge_case=is_edge_case,
    )


@pytest.fixture
def config() -> BenchmarkConfig:
    return BenchmarkConfig(interaction_count=5, time_budget_seconds=120, random_seed=42)


@pytest.fixture
def trace_writer(tmp_path) -> MagicMock:
    tw = MagicMock()
    tw.output_path = tmp_path / "trace.jsonl"
    tw.output_path.touch()
    return tw


class TestCoherence:
    """Test the static _compute_coherence method."""

    def test_empty_response(self):
        score = BenchmarkSessionExecutor._compute_coherence("", "catalog")
        assert score == 0.0

    def test_short_response(self):
        score = BenchmarkSessionExecutor._compute_coherence("Too short", "catalog")
        assert score == 0.0

    def test_response_with_domain_keywords(self):
        text = "I found the book titled 'Elephants of the Savanna' by the author you requested. The ISBN is 978-123."
        score = BenchmarkSessionExecutor._compute_coherence(text, "catalog")
        assert score > 0.3

    def test_error_response(self):
        text = "Internal Server Error: Something went wrong with the traceback."
        score = BenchmarkSessionExecutor._compute_coherence(text, "catalog")
        assert score == 0.1

    def test_no_domain_keywords_gets_moderate_score(self):
        text = "Here is a response that is sufficiently long but doesn't match any domain keywords at all."
        score = BenchmarkSessionExecutor._compute_coherence(text, "catalog")
        # Should get some credit for length but penalized for no keywords
        assert 0.0 < score < 0.8

    def test_circulation_domain_keywords(self):
        text = "Your checkout is confirmed. The book is due back in 14 days. Your patron account has been updated."
        score = BenchmarkSessionExecutor._compute_coherence(text, "circulation")
        assert score > 0.3


class TestHallucinationDetection:
    """Test _detect_hallucination method."""

    def test_no_hallucination_with_known_title(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=["Tusks of Thunder"],
        )
        result = executor._detect_hallucination("The book 'Tusks of Thunder' is available.")
        assert result is False

    def test_hallucination_with_unknown_title(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=["Tusks of Thunder"],
        )
        result = executor._detect_hallucination("The book 'Ivory Dreams of Forever' is a great read.")
        assert result is True

    def test_no_hallucination_when_no_quotes(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=["Tusks of Thunder"],
        )
        result = executor._detect_hallucination("I found some books for you in the catalog.")
        assert result is False

    def test_no_hallucination_when_empty_known_titles(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=[],
        )
        result = executor._detect_hallucination("The book 'Unknown Title' is here.")
        assert result is False

    def test_skips_common_non_title_phrases(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=["Tusks of Thunder"],
        )
        result = executor._detect_hallucination("Your 'library account' has been updated.")
        assert result is False


class TestRefusalDetection:
    """Test _detect_refusal method."""

    def test_detects_blocked(self):
        assert BenchmarkSessionExecutor._detect_refusal("Your account is blocked.")

    def test_detects_unable(self):
        assert BenchmarkSessionExecutor._detect_refusal("I am unable to process that.")

    def test_no_refusal_in_normal_response(self):
        assert not BenchmarkSessionExecutor._detect_refusal("Here is your book information.")

    def test_empty_response(self):
        assert not BenchmarkSessionExecutor._detect_refusal("")


class TestExecuteInteraction:
    """Test _execute_interaction with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_successful_interaction(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
            known_book_titles=["Tusks of Thunder"],
        )
        interaction = _make_interaction()

        mock_response = httpx.Response(
            200,
            json={"response": "Here is the book you requested.", "session_id": "sess-001"},
        )

        with patch("agents.benchmark_session_executor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await executor._execute_interaction(interaction)

        assert result.status == "completed"
        assert result.agent_response == "Here is the book you requested."
        assert result.duration_ms > 0
        # Trace should have start and end calls
        assert trace_writer.emit.call_count >= 2

    @pytest.mark.asyncio
    async def test_timeout_interaction(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
        )
        interaction = _make_interaction()

        with patch("agents.benchmark_session_executor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timed out")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await executor._execute_interaction(interaction)

        assert result.status == "timeout"
        assert result.error == "Timeout"

    @pytest.mark.asyncio
    async def test_error_interaction(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
        )
        interaction = _make_interaction()

        with patch("agents.benchmark_session_executor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = RuntimeError("connection refused")
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await executor._execute_interaction(interaction)

        assert result.status == "error"
        assert "connection refused" in result.error


class TestTimeBudget:
    """Test time budget enforcement."""

    @pytest.mark.asyncio
    async def test_stops_when_budget_exceeded(self, trace_writer):
        config = BenchmarkConfig(
            interaction_count=100,
            time_budget_seconds=30,  # Minimal valid budget
            random_seed=42,
        )
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
        )
        # Simulate budget already used by patching time.monotonic
        interactions = [_make_interaction(interaction_id=f"bm-{i:04d}") for i in range(10)]

        # Patch time.monotonic to simulate elapsed time exceeding budget
        call_count = 0
        original_monotonic = time.monotonic

        def fake_monotonic():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0.0  # start_time
            return 100.0  # Way past budget on every check

        with patch("agents.benchmark_session_executor.time.monotonic", side_effect=fake_monotonic):
            results, metrics = await executor.execute(interactions)

        assert len(results) == 0  # Budget exceeded on first check


class TestSessionCaching:
    """Test session reuse for stateful sequences."""

    @pytest.mark.asyncio
    async def test_session_cached_for_sequence(self, config, trace_writer):
        executor = BenchmarkSessionExecutor(
            config=config,
            trace_writer=trace_writer,
        )

        ix1 = _make_interaction(interaction_id="bm-0001", sequence_id="seq-0001")
        ix2 = _make_interaction(interaction_id="bm-0002", sequence_id="seq-0001")

        mock_response = httpx.Response(
            200,
            json={"response": "Done.", "session_id": "cached-session-001"},
        )

        with patch("agents.benchmark_session_executor.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            await executor._execute_interaction(ix1)
            assert executor._session_cache.get("seq-0001") == "cached-session-001"

            await executor._execute_interaction(ix2)
            # Second call should have included session_id in body
            second_call_body = mock_client.post.call_args_list[1][1].get("json", {})
            assert second_call_body.get("session_id") == "cached-session-001"


class TestAggregateMetrics:
    """Test BenchmarkAggregateMetrics defaults."""

    def test_defaults(self):
        m = BenchmarkAggregateMetrics()
        assert m.total_interactions == 0
        assert m.completed == 0
        assert m.errored == 0
        assert m.timed_out == 0
        assert m.tool_engaged_count == 0
        assert m.hallucination_count == 0
        assert m.domain_breakdown == {}
