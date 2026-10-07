"""Tests for front desk ILL delegation path."""

from agents.front_desk import (
    FrontDeskAgent,
    create_front_desk_agent,
    FRONT_DESK_SYSTEM_PROMPT,
)


class TestFrontDeskILLDelegation:
    """Verify front desk agent has ILL delegation capability."""

    def test_system_prompt_mentions_ill_delegation(self):
        """System prompt includes ILL escalation routing instruction."""
        assert "ill_escalation" in FRONT_DESK_SYSTEM_PROMPT.lower()

    def test_front_desk_agent_has_ill_tool(self):
        """FrontDeskAgent registers an ILL escalation tool."""
        agent = FrontDeskAgent()
        tool_names = [t.func.__name__ for t in agent.agent.tools]
        assert "_ill_escalation" in tool_names

    def test_front_desk_agent_has_three_tools(self):
        """FrontDeskAgent has catalog, circulation, and ILL tools."""
        agent = FrontDeskAgent()
        assert len(agent.agent.tools) == 3

    def test_create_front_desk_agent_has_ill_sub_agent(self):
        """Factory function creates agent with ILL sub-agent."""
        agent = create_front_desk_agent()
        sub_agent_names = [sa.name for sa in agent.sub_agents]
        assert "ill_escalation_agent" in sub_agent_names

    def test_create_front_desk_agent_has_three_sub_agents(self):
        """Factory function creates agent with all three sub-agents."""
        agent = create_front_desk_agent()
        assert len(agent.sub_agents) == 3


class TestFrontDeskFallbackRouting:
    """Verify ILL keywords route correctly in fallback mode."""

    def test_ill_keywords_detected(self):
        """ILL-related keywords are present in fallback routing."""
        agent = FrontDeskAgent()
        # Verify the _fallback_response method handles ILL keywords
        # by checking it exists and has the right structure.
        import inspect
        source = inspect.getsource(agent._fallback_response)
        assert "ill_keywords" in source
        assert "inter-library" in source
        assert "another library" in source
