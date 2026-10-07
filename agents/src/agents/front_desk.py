"""Front Desk Agent - ADK-based main orchestrator that interacts with patrons."""

import logging
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from agents.config import EVAL_SHORTCUTS_ENABLED, REFUSAL_MARKERS, PATRON_ID_PROMPT_MARKERS
from agents.models.factory import build_model_adapter
from agents.session.active_patron_context import get_active_patron_context
from agents.catalog_agent import CatalogAgent, create_catalog_agent
from agents.circulation_agent import CirculationAgent, create_circulation_agent
from agents.ill_escalation_agent import ILLEscalationAgent, create_ill_escalation_agent
from agents.utils import run_agent_text
from shared.eval.runtime_trace import begin_tool_call, end_tool_call

logger = logging.getLogger(__name__)


FRONT_DESK_SYSTEM_PROMPT = """You are the Front Desk Librarian at the Hanno Memorial Library, located in the historic Pachydon District. The Library is a monument to "Long Memory" — the cultural belief that elephants never forget, and neither should their records.

CRITICAL RULES:
1. You have NO knowledge of books. You must ALWAYS use tools to search the catalog.
2. NEVER make up book titles, authors, or details. If you don't find it, say so.
3. Our collection contains works from the Hanno Memorial catalog — verse tragedies by Maren Greyhorn, histories by Dr. H. Caladent, children's tales by Penelope Trunkling, and more. These are unique to our Archive.
4. If a patron asks about real-world books (e.g., "1984", "Harry Potter", "Pride and Prejudice"), explain that our collection is specialized and search anyway to confirm we don't have it.
5. We are part of the Great Herd Library System (GHLS). For items not in our collection, suggest checking other member libraries.
6. Account questions are bound to the active patron profile for this chat session.
7. Do not ask for patron ID if active profile context exists.
8. If asked to access a different patron's account, instruct the user to switch active profile first.

Your personality:
- Friendly, helpful, and knowledgeable about the Pachydon District
- Professional but warm, embodying the Library's "Long Memory" values
- Patient with all types of questions

Our Collection Strata:
- Stratum 1: Noble Tragedies (verse dramas, tragic histories)
- Stratum 2: Histories & Memoirs (historical works, biographical accounts)
- Stratum 3: Modern Literary Works (contemporary fiction)
- Stratum 4: Technical & Reference (scholarly works, nonfiction)
- Stratum 5: Children's Tales (fables, picture books, early readers)
- Stratum 6: Poetry Collections (sonnets, odes, verse)
- Stratum 7: Philosophy & Treatises (ethics, philosophy)
- Stratum 8: Translated Works (foreign authors, translations)
- Stratum 9: Extended Tragedies (additional verse dramas)
- Stratum 10: Extended Histories (additional historical works)
- Stratum 11: Extended Modern Literary (additional contemporary fiction)
- Stratum 12: Extended Technical (additional scholarly works)
- Stratum 13: Genre Fiction (mystery, romance, adventure)

Key Authors in Our Collection:
- Maren Greyhorn, J. Temberton, Lady Ossifer Wryte (tragedies)
- Dr. H. Caladent, P.R. Mammora (histories)
- Lila Trent, Marcus Okoye (modern)
- Penelope Trunkling, Mama Mammoth, Cornelius Stomper (children's)

When delegating:
- Catalog questions → Use catalog_search tool
- Checkout/return/hold questions → Use circulation_action tool
- Inter-library loan / books not in our catalog → Use ill_escalation tool

Library Policies:
- Standard loan period: 14 days
- Renewals: Up to 2 times (unless holds are waiting)
- Overdue fines: $0.25 per day
- Checkout blocked if fines exceed $10

Always be helpful and guide patrons to the right resources. Remember: we are a specialized archive, not a general bookstore."""


def create_front_desk_agent(
    catalog_agent: Optional[LlmAgent] = None,
    circulation_agent: Optional[LlmAgent] = None,
    ill_agent: Optional[LlmAgent] = None,
) -> LlmAgent:
    """Create a Front Desk Agent using ADK LlmAgent with sub-agents.

    Args:
        catalog_agent: Optional pre-configured catalog agent
        circulation_agent: Optional pre-configured circulation agent
        ill_agent: Optional pre-configured ILL escalation agent

    Returns:
        Configured LlmAgent instance for front desk operations
    """
    # Use provided agents or create new ones
    catalog = catalog_agent or create_catalog_agent()
    circulation = circulation_agent or create_circulation_agent()
    ill = ill_agent or create_ill_escalation_agent()
    model_ref = build_model_adapter().to_adk_model_ref()

    # Create the front desk agent with sub-agents
    agent = LlmAgent(
        model=model_ref,
        name="front_desk_agent",
        description="Main patron-facing librarian for the Hanno Memorial Library",
        instruction=FRONT_DESK_SYSTEM_PROMPT,
        sub_agents=[catalog, circulation, ill],
        output_key="front_desk_response",
    )

    logger.info("Created FrontDeskAgent with ADK LlmAgent and sub-agents")
    return agent


class FrontDeskAgent:
    """Main patron-facing agent that orchestrates specialist agents.

    This class provides a wrapper around the ADK LlmAgent for backward compatibility
    with existing code that uses the FrontDeskAgent class directly.

    Maintains conversation history for multi-turn conversations.
    """

    def __init__(self):
        model_ref = build_model_adapter().to_adk_model_ref()
        # Create sub-agents
        self._catalog_agent = CatalogAgent()
        self._circulation_agent = CirculationAgent()
        self._ill_agent = ILLEscalationAgent()

        # Create delegation tools that route to sub-agents
        # Note: FunctionTool derives name and description from the function docstrings
        self._catalog_tool = FunctionTool(func=self._catalog_search)
        self._circulation_tool = FunctionTool(func=self._circulation_action)
        self._ill_tool = FunctionTool(func=self._ill_escalation)

        # Create the main agent with delegation tools
        self._agent = LlmAgent(
            model=model_ref,
            name="front_desk_agent",
            description="Main patron-facing librarian for the Hanno Memorial Library",
            instruction=FRONT_DESK_SYSTEM_PROMPT,
            tools=[self._catalog_tool, self._circulation_tool, self._ill_tool],
            output_key="front_desk_response",
        )

        # Conversation history for multi-turn support
        self._conversation_history: list[dict] = []

        logger.info("Created FrontDeskAgent with ADK LlmAgent")

    async def _catalog_search(self, query: str) -> str:
        """Delegate catalog search to catalog agent."""
        call_id, started = begin_tool_call(
            source="agents.front_desk",
            tool_name="delegate_catalog_agent",
            input_payload={"query": query},
        )
        try:
            response = await self._catalog_agent.process(query)
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_catalog_agent",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"response_preview": response[:280]},
            )
            return response
        except Exception as exc:
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_catalog_agent",
                call_id=call_id,
                started=started,
                success=False,
                error=str(exc),
            )
            raise

    async def _circulation_action(self, query: str) -> str:
        """Delegate circulation actions to circulation agent."""
        call_id, started = begin_tool_call(
            source="agents.front_desk",
            tool_name="delegate_circulation_agent",
            input_payload={"query": query},
        )
        try:
            response = await self._circulation_agent.process(query)
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_circulation_agent",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"response_preview": response[:280]},
            )
            return response
        except Exception as exc:
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_circulation_agent",
                call_id=call_id,
                started=started,
                success=False,
                error=str(exc),
            )
            raise

    async def _ill_escalation(self, query: str) -> str:
        """Delegate inter-library loan inquiries to ILL escalation agent."""
        call_id, started = begin_tool_call(
            source="agents.front_desk",
            tool_name="delegate_ill_escalation_agent",
            input_payload={"query": query},
        )
        try:
            response = await self._ill_agent.process(query)
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_ill_escalation_agent",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"response_preview": response[:280]},
            )
            return response
        except Exception as exc:
            end_tool_call(
                source="agents.front_desk",
                tool_name="delegate_ill_escalation_agent",
                call_id=call_id,
                started=started,
                success=False,
                error=str(exc),
            )
            raise

    @property
    def agent(self) -> LlmAgent:
        """Get the underlying ADK LlmAgent."""
        return self._agent

    @property
    def catalog_agent(self) -> CatalogAgent:
        """Get the catalog sub-agent."""
        return self._catalog_agent

    @property
    def circulation_agent(self) -> CirculationAgent:
        """Get the circulation sub-agent."""
        return self._circulation_agent

    def reset_conversation(self) -> None:
        """Clear conversation history for a new session."""
        self._conversation_history = []
        logger.debug("Conversation history cleared")

    async def chat(self, message: str) -> str:
        """Process a chat message from a patron.

        Args:
            message: The patron's message

        Returns:
            The librarian's response
        """
        return await self.chat_with_context(message)

    async def chat_with_context(
        self,
        message: str,
        *,
        session_id: str | None = None,
        user_id: str | None = None,
    ) -> str:
        """Process a message with optional runtime session/user context."""
        try:
            # Add user message to history
            self._conversation_history.append({
                "role": "user",
                "content": message,
            })

            # Build context from history for the agent
            context = self._build_context()

            shortcut_response = None
            if EVAL_SHORTCUTS_ENABLED:
                shortcut_response = await self._identity_bound_shortcut(message)

            if shortcut_response is not None:
                response = shortcut_response
            else:
                # Run ADK agent via compatibility helper.
                try:
                    response = await run_agent_text(
                        agent=self._agent,
                        message=context,
                        app_name="front-desk-agent",
                        session_id=session_id or "front-desk-session",
                        user_id=user_id or "local-user",
                    )
                    if EVAL_SHORTCUTS_ENABLED and self._should_force_identity_fallback(message, response):
                        response = await self._fallback_response(message)
                except Exception as adk_error:
                    logger.warning("FrontDeskAgent ADK runtime failed: %s", adk_error)
                    if EVAL_SHORTCUTS_ENABLED:
                        response = await self._fallback_response(message)
                    else:
                        raise

            # Add assistant response to history
            self._conversation_history.append({
                "role": "assistant",
                "content": response,
            })

            return response

        except Exception as e:
            logger.error(f"FrontDeskAgent error: {e}")
            return "I'm having trouble processing that. Could you try rephrasing?"

    async def _identity_bound_shortcut(self, message: str) -> str | None:
        """Deterministically route identity-bound prompts before model generation."""
        lowered = message.lower()
        active_context = get_active_patron_context()
        if not active_context:
            return None

        if "who am i" in lowered or "logged in as" in lowered or "active profile" in lowered:
            label = active_context.name or active_context.patron_id
            return f"You are currently using patron profile {label} ({active_context.patron_id})."

        if not self._is_identity_bound_query(lowered):
            return None

        if self._is_ill_account_query(lowered):
            return await self._ill_escalation(message)

        if self._is_circulation_account_query(lowered):
            return await self._circulation_action(message)

        return None

    def _should_force_identity_fallback(self, message: str, response: str) -> bool:
        """Decide if we should bypass model output for identity-bound prompts."""
        lowered_response = response.lower()
        if any(marker in lowered_response for marker in REFUSAL_MARKERS):
            return True

        active_context = get_active_patron_context()
        if not active_context:
            return False

        if not self._is_identity_bound_query(message.lower()):
            return False

        return any(marker in lowered_response for marker in PATRON_ID_PROMPT_MARKERS)

    @staticmethod
    def _has_self_reference(lowered: str) -> bool:
        return any(token in lowered for token in (" my ", " my", "i ", " i", " me", " me ", "i'm", "im "))

    def _is_identity_bound_query(self, lowered: str) -> bool:
        if "who am i" in lowered or "logged in as" in lowered:
            return True
        if not self._has_self_reference(lowered):
            return False
        account_terms = (
            "checked out",
            "checkout",
            "account",
            "status",
            "fine",
            "fines",
            "ill request",
            "inter-library",
            "ill ",
        )
        return any(term in lowered for term in account_terms)

    @staticmethod
    def _is_ill_account_query(lowered: str) -> bool:
        if "ill" not in lowered and "inter-library" not in lowered:
            return False
        return any(term in lowered for term in ("status", "request", "requests", "pending", "approved"))

    @staticmethod
    def _is_circulation_account_query(lowered: str) -> bool:
        circulation_terms = (
            "checkout",
            "checked out",
            "fine",
            "fines",
            "account",
            "status",
            "hold",
            "renew",
            "return",
        )
        return any(term in lowered for term in circulation_terms)

    async def _fallback_response(self, message: str) -> str:
        """Fallback routing when ADK runtime/model execution is unavailable."""
        lowered = message.lower()
        active_context = get_active_patron_context()

        if ("who am i" in lowered or "logged in" in lowered) and active_context:
            label = active_context.name or active_context.patron_id
            return f"You are currently using patron profile {label} ({active_context.patron_id})."

        ill_keywords = (
            "inter-library",
            "interlibrary",
            "ill ",
            "borrow from",
            "another library",
            "other library",
            "partner library",
            "other libraries",
        )
        circulation_keywords = (
            "checkout",
            "check out",
            "renew",
            "return",
            "hold",
            "fine",
            "patron",
            "account",
            "who am i",
            "logged in",
            "checked out",
            "fines",
        )

        if any(keyword in lowered for keyword in ill_keywords):
            return await self._ill_escalation(message)

        if any(keyword in lowered for keyword in circulation_keywords):
            return await self._circulation_action(message)

        return await self._catalog_search(message)

    def _build_context(self) -> str:
        """Build context string from conversation history.

        Returns:
            Formatted context for the agent
        """
        if len(self._conversation_history) <= 1:
            # Just the current message
            return self._conversation_history[-1]["content"]

        # Include recent history for context
        parts = []
        for msg in self._conversation_history[-10:]:  # Last 10 messages
            role = msg["role"].capitalize()
            parts.append(f"{role}: {msg['content']}")

        return "\n".join(parts)


# Convenience function for simple usage
async def chat_with_librarian(
    message: str, agent: Optional[FrontDeskAgent] = None
) -> tuple[str, FrontDeskAgent]:
    """Chat with the AI librarian.

    Args:
        message: The patron's message
        agent: Optional existing agent instance for conversation continuity

    Returns:
        Tuple of (response, agent) for maintaining conversation state
    """
    if agent is None:
        agent = FrontDeskAgent()
    response = await agent.chat(message)
    return response, agent
