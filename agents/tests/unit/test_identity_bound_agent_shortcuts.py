"""Unit tests for deterministic identity-bound shortcuts in agent routing."""

import pytest

from agents import circulation_agent, front_desk, ill_escalation_agent
from agents.session.active_patron_context import bind_active_patron_context


class TestFrontDeskIdentityShortcut:
    """Verify front desk handles active-profile identity prompts directly."""

    @pytest.mark.asyncio
    async def test_who_am_i_is_answered_without_model_call(self, monkeypatch):
        """Who-am-I should resolve directly from active profile context."""
        monkeypatch.setattr(front_desk, "EVAL_SHORTCUTS_ENABLED", True)

        async def _unexpected_run_agent_text(**_kwargs):  # pragma: no cover - defensive guard
            raise AssertionError("Model path should not run for who-am-I shortcut.")

        monkeypatch.setattr(front_desk, "run_agent_text", _unexpected_run_agent_text)
        agent = front_desk.FrontDeskAgent()

        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            response = await agent.chat_with_context("Who am I currently logged in as?")

        assert "patron-001" in response
        assert "Trunsworth Greyvale" in response


class TestCirculationIdentityShortcut:
    """Verify circulation agent identity-bound account behavior."""

    @pytest.mark.asyncio
    async def test_summary_query_uses_active_profile_context(self, monkeypatch):
        """Summary request should use active profile tool and avoid patron-id prompts."""
        monkeypatch.setattr(circulation_agent, "EVAL_SHORTCUTS_ENABLED", True)

        async def _fake_summary() -> dict:
            return {
                "patron": {"id": "patron-001", "name": "Trunsworth Greyvale"},
                "checkouts": [{"instance_id": "inst-001-a"}],
                "holds": [],
                "total_fines_owed": "0.00",
            }

        async def _unexpected_run_agent_text(**_kwargs):  # pragma: no cover - defensive guard
            raise AssertionError("Model path should not run for identity-bound summary.")

        monkeypatch.setattr(circulation_agent, "get_my_patron_summary", _fake_summary)
        monkeypatch.setattr(circulation_agent, "run_agent_text", _unexpected_run_agent_text)

        agent = circulation_agent.CirculationAgent()
        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            response = await agent.process("What books do I have checked out?")

        assert "1 active checkout" in response
        assert "inst-001-a" in response
        assert "patron id" not in response.lower()

    @pytest.mark.asyncio
    async def test_checkout_prompt_requests_instance_only(self, monkeypatch):
        """Checkout intent without an instance id should not ask for patron id."""
        monkeypatch.setattr(circulation_agent, "EVAL_SHORTCUTS_ENABLED", True)
        agent = circulation_agent.CirculationAgent()
        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            response = await agent.process("Please check it out to me.")

        lowered = response.lower()
        assert "instance id" in lowered
        assert "patron id" not in lowered


class TestIllIdentityShortcut:
    """Verify ILL status queries resolve from active profile context."""

    @pytest.mark.asyncio
    async def test_list_my_ill_requests_shortcut(self, monkeypatch):
        """ILL status query should list active-profile requests without asking patron id."""
        monkeypatch.setattr(ill_escalation_agent, "EVAL_SHORTCUTS_ENABLED", True)

        async def _fake_list_my_ill_requests(status: str | None = None) -> dict:
            del status
            return {
                "requests": [
                    {
                        "id": "ill-req-123",
                        "status": "requested",
                        "source_library": "mammoth-valley",
                        "book_title": "The Echoes of Time",
                    }
                ]
            }

        async def _unexpected_run_agent_text(**_kwargs):  # pragma: no cover - defensive guard
            raise AssertionError("Model path should not run for identity-bound ILL status.")

        monkeypatch.setattr(ill_escalation_agent, "list_my_ill_requests", _fake_list_my_ill_requests)
        monkeypatch.setattr(ill_escalation_agent, "run_agent_text", _unexpected_run_agent_text)

        agent = ill_escalation_agent.ILLEscalationAgent()
        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            response = await agent.process("Check the status of my ILL requests.")

        assert "ill-req-123" in response
        assert "requested" in response.lower()
        assert "patron id" not in response.lower()
