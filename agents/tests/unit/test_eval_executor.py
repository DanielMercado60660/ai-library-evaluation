"""Unit tests for EvalScriptExecutor assertion logic and step execution."""

import json
import pytest

from agents.eval_executor import (
    AssertionResult,
    EvalScriptExecutor,
    EvalStepResult,
    EvalScenarioResult,
)
from shared.eval.eval_script_schemas import EvalScript, EvalStep, StepAssertion


# ---------------------------------------------------------------------------
# Static helper tests (no I/O)
# ---------------------------------------------------------------------------


class TestCheckResponseContent:
    """Test _check_response_content static method."""

    def test_must_contain_found(self):
        results = EvalScriptExecutor._check_response_content(
            "The book 'Tusk and Bone' is available in our catalog.",
            must_contain=["Tusk and Bone"],
            must_not_contain=[],
        )
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].assertion_type == "content_contains"

    def test_must_contain_not_found(self):
        results = EvalScriptExecutor._check_response_content(
            "The book is available.",
            must_contain=["Tusk and Bone"],
            must_not_contain=[],
        )
        assert len(results) == 1
        assert results[0].passed is False

    def test_must_contain_case_insensitive(self):
        results = EvalScriptExecutor._check_response_content(
            "The book TUSK AND BONE is available.",
            must_contain=["tusk and bone"],
            must_not_contain=[],
        )
        assert results[0].passed is True

    def test_must_not_contain_absent(self):
        results = EvalScriptExecutor._check_response_content(
            "Here is your checkout status.",
            must_contain=[],
            must_not_contain=["I don't know"],
        )
        assert len(results) == 1
        assert results[0].passed is True
        assert results[0].assertion_type == "content_not_contains"

    def test_must_not_contain_present(self):
        results = EvalScriptExecutor._check_response_content(
            "I don't know about that book.",
            must_contain=[],
            must_not_contain=["I don't know"],
        )
        assert len(results) == 1
        assert results[0].passed is False

    def test_multiple_assertions(self):
        results = EvalScriptExecutor._check_response_content(
            "Your fine of $2.50 has been recorded.",
            must_contain=["fine", "$2.50"],
            must_not_contain=["error", "not found"],
        )
        assert len(results) == 4
        assert all(r.passed for r in results)

    def test_empty_lists(self):
        results = EvalScriptExecutor._check_response_content(
            "Any response",
            must_contain=[],
            must_not_contain=[],
        )
        assert len(results) == 0


class TestCheckToolCalls:
    """Test _check_tool_calls method."""

    def setup_method(self):
        self.executor = EvalScriptExecutor()

    def test_all_expected_found(self):
        results = self.executor._check_tool_calls(
            expected=["search_books", "get_book_details"],
            observed=["search_books", "get_book_details", "extra_tool"],
        )
        assert len(results) == 2
        assert all(r.passed for r in results)
        assert all(r.assertion_type == "tool_call" for r in results)

    def test_expected_not_found(self):
        results = self.executor._check_tool_calls(
            expected=["search_books", "checkout_book"],
            observed=["search_books"],
        )
        assert len(results) == 2
        assert results[0].passed is True  # search_books found
        assert results[1].passed is False  # checkout_book not found

    def test_empty_expected(self):
        results = self.executor._check_tool_calls(
            expected=[],
            observed=["search_books"],
        )
        assert len(results) == 0

    def test_empty_observed(self):
        results = self.executor._check_tool_calls(
            expected=["search_books"],
            observed=[],
        )
        assert len(results) == 1
        assert results[0].passed is False


class TestResolveFieldPath:
    """Test _resolve_field_path static method."""

    def test_simple_key(self):
        data = {"total": 5}
        assert EvalScriptExecutor._resolve_field_path(data, "total") == 5

    def test_nested_key(self):
        data = {"patron": {"name": "Trunsworth"}}
        assert EvalScriptExecutor._resolve_field_path(data, "patron.name") == "Trunsworth"

    def test_list_index(self):
        data = {"items": [{"status": "active"}, {"status": "returned"}]}
        assert EvalScriptExecutor._resolve_field_path(data, "items.0.status") == "active"
        assert EvalScriptExecutor._resolve_field_path(data, "items.1.status") == "returned"

    def test_missing_key_returns_none(self):
        data = {"patron": {"name": "Trunsworth"}}
        assert EvalScriptExecutor._resolve_field_path(data, "patron.age") is None

    def test_invalid_list_index_returns_none(self):
        data = {"items": [1, 2]}
        assert EvalScriptExecutor._resolve_field_path(data, "items.5") is None

    def test_non_numeric_list_index_returns_none(self):
        data = {"items": [1, 2]}
        assert EvalScriptExecutor._resolve_field_path(data, "items.foo") is None


class TestValuesMatch:
    """Test _values_match static method."""

    def test_exact_match(self):
        assert EvalScriptExecutor._values_match("hello", "hello") is True

    def test_numeric_coercion(self):
        assert EvalScriptExecutor._values_match(5, 5.0) is True
        assert EvalScriptExecutor._values_match("5", 5) is True

    def test_string_coercion(self):
        assert EvalScriptExecutor._values_match(True, "True") is True

    def test_no_match(self):
        assert EvalScriptExecutor._values_match("hello", "world") is False

    def test_none_values(self):
        assert EvalScriptExecutor._values_match(None, None) is True
        assert EvalScriptExecutor._values_match(None, "something") is False


# ---------------------------------------------------------------------------
# Step execution tests (mocked httpx)
# ---------------------------------------------------------------------------


class TestExecuteStep:
    """Test _execute_step with mocked HTTP."""

    @pytest.mark.asyncio
    async def test_step_passes_with_matching_content(self, monkeypatch):
        executor = EvalScriptExecutor()

        async def _mock_send(self_, message, session_id, patron_id, patron_name, patron_role, timeout):
            return "The book Tusk and Bone is available in our catalog.", "sess-001"

        monkeypatch.setattr(EvalScriptExecutor, "_send_chat_message", _mock_send)

        step = EvalStep(
            step_id="test_step",
            order=1,
            patron_message="Do you have Tusk and Bone?",
            response_must_contain=["Tusk and Bone"],
            response_must_not_contain=["I don't know"],
        )

        result, session_id = await executor._execute_step(
            step=step,
            session_id=None,
            patron_id="patron-001",
            patron_name="Test Patron",
            patron_role="patron",
            scenario_id="test_scenario",
        )

        assert result.passed is True
        assert session_id == "sess-001"
        assert len(result.assertions) == 2
        assert all(a.passed for a in result.assertions)

    @pytest.mark.asyncio
    async def test_step_fails_when_content_missing(self, monkeypatch):
        executor = EvalScriptExecutor()

        async def _mock_send(self_, message, session_id, patron_id, patron_name, patron_role, timeout):
            return "I'm sorry, I don't have that information.", "sess-001"

        monkeypatch.setattr(EvalScriptExecutor, "_send_chat_message", _mock_send)

        step = EvalStep(
            step_id="test_step",
            order=1,
            patron_message="Do you have Tusk and Bone?",
            response_must_contain=["Tusk and Bone"],
        )

        result, _ = await executor._execute_step(
            step=step,
            session_id=None,
            patron_id="patron-001",
            patron_name="Test",
            patron_role="patron",
            scenario_id="test_scenario",
        )

        assert result.passed is False
        assert any(not a.passed for a in result.assertions)

    @pytest.mark.asyncio
    async def test_step_records_error_on_exception(self, monkeypatch):
        executor = EvalScriptExecutor()

        async def _mock_send(self_, message, session_id, patron_id, patron_name, patron_role, timeout):
            raise RuntimeError("Connection refused")

        monkeypatch.setattr(EvalScriptExecutor, "_send_chat_message", _mock_send)

        step = EvalStep(
            step_id="test_step",
            order=1,
            patron_message="Hello",
        )

        result, _ = await executor._execute_step(
            step=step,
            session_id=None,
            patron_id="patron-001",
            patron_name="Test",
            patron_role="patron",
            scenario_id="test_scenario",
        )

        assert result.passed is False
        assert result.error is not None
        assert "Connection refused" in result.error


class TestExecuteScenario:
    """Test execute_scenario with mocked steps."""

    @pytest.mark.asyncio
    async def test_full_scenario_passes(self, monkeypatch):
        executor = EvalScriptExecutor()

        call_count = 0

        async def _mock_send(self_, message, session_id, patron_id, patron_name, patron_role, timeout):
            nonlocal call_count
            call_count += 1
            return f"Response to step {call_count}", session_id or "sess-new"

        monkeypatch.setattr(EvalScriptExecutor, "_send_chat_message", _mock_send)

        script = EvalScript(
            scenario_id="test_scenario",
            patron_id="patron-001",
            patron_name="Test User",
            steps=[
                EvalStep(step_id="step_1", order=1, patron_message="Hello"),
                EvalStep(step_id="step_2", order=2, patron_message="Find a book"),
            ],
        )

        result = await executor.execute_scenario("test_scenario", script)

        assert result.scenario_id == "test_scenario"
        assert len(result.steps) == 2
        assert result.passed is True
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_scenario_fails_when_step_fails(self, monkeypatch):
        executor = EvalScriptExecutor()

        async def _mock_send(self_, message, session_id, patron_id, patron_name, patron_role, timeout):
            return "I don't know", session_id or "sess-new"

        monkeypatch.setattr(EvalScriptExecutor, "_send_chat_message", _mock_send)

        script = EvalScript(
            scenario_id="test_scenario",
            patron_id="patron-001",
            patron_name="Test User",
            steps=[
                EvalStep(
                    step_id="step_1",
                    order=1,
                    patron_message="Hello",
                    response_must_contain=["Tusk and Bone"],  # Won't be found
                ),
            ],
        )

        result = await executor.execute_scenario("test_scenario", script)

        assert result.passed is False
        assert result.total_assertions > 0
        assert result.passed_assertions < result.total_assertions
