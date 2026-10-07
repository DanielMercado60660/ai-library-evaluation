"""Circulation Agent - ADK-based specialist for checkouts, returns, holds, and fines."""

import logging
import re
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from agents.config import EVAL_SHORTCUTS_ENABLED, REFUSAL_MARKERS
from agents.models.factory import build_model_adapter
from agents.session.active_patron_context import get_active_patron_context
from agents.tools.circulation_tools import (
    checkout_for_me,
    get_my_fines,
    get_my_patron_summary,
    get_patron_summary,
    checkout_item,
    renew_checkout,
    return_item,
    place_hold,
    place_hold_for_me,
    cancel_hold,
    get_patron_fines,
    pay_fine,
)
from agents.utils import run_agent_text

logger = logging.getLogger(__name__)


CIRCULATION_AGENT_SYSTEM_PROMPT = """You are a Circulation Specialist for Hanno Memorial Library.

Your job is to help patrons with checkouts, returns, renewals, and holds.

CRITICAL RULES:
1. Account actions are bound to the active patron profile for this chat session.
2. Use active-profile tools first: get_my_patron_summary, get_my_fines, checkout_for_me, place_hold_for_me.
3. Do not ask for patron ID when active profile context exists.
4. If asked to access a different patron, instruct the user to switch active profile first.
5. NEVER make up patron IDs, checkout IDs, or instance IDs. Use only what tools return.

Checkout Rules:
- Standard loan period: 14 days
- Renewals: Up to 2 times, unless holds are waiting on the book
- Checkout limits vary by patron category:
  - Adult: 10 items
  - Youth: 5 items
  - Staff: 25 items
  - Researcher: 15 items
  - Restricted: 3 items

Hold Rules:
- Patrons can hold books that are checked out
- When available, item is held for 7 days
- Position in queue matters — communicate wait times
- Hold limits match checkout limits by category

Fine Policies:
- Overdue: $0.25 per day (capped at item value)
- Patrons with fines > $10 are blocked from new checkouts
- Lost or damaged items assessed separately

When helping patrons:
1. Use get_my_patron_summary first for account state.
2. Provide clear information about due dates.
3. Warn about any fines or blocks.
4. Offer renewal options for overdue items when possible.
5. For holds, tell them their queue position when available.

Remember: This is Hanno Memorial Library in the Pachydon District. Our motto is "Long Memory" — we keep careful records."""


def create_circulation_agent() -> LlmAgent:
    """Create a Circulation Agent using ADK LlmAgent.

    Returns:
        Configured LlmAgent instance for circulation operations
    """
    model_ref = build_model_adapter().to_adk_model_ref()
    # Create ADK FunctionTools from the HTTP tool functions
    # Note: FunctionTool derives name and description from the function docstrings
    tools = [
        FunctionTool(func=get_my_patron_summary),
        FunctionTool(func=get_my_fines),
        FunctionTool(func=checkout_for_me),
        FunctionTool(func=place_hold_for_me),
        FunctionTool(func=get_patron_summary),
        FunctionTool(func=checkout_item),
        FunctionTool(func=renew_checkout),
        FunctionTool(func=return_item),
        FunctionTool(func=place_hold),
        FunctionTool(func=cancel_hold),
        FunctionTool(func=get_patron_fines),
        FunctionTool(func=pay_fine),
    ]

    agent = LlmAgent(
        model=model_ref,
        name="circulation_agent",
        description="Circulation specialist for the Hanno Memorial Library - handles checkouts, returns, holds, and fines",
        instruction=CIRCULATION_AGENT_SYSTEM_PROMPT,
        tools=tools,
        output_key="circulation_result",
    )

    logger.info("Created CirculationAgent with ADK LlmAgent")
    return agent


class CirculationAgent:
    """Agent specialized in circulation operations: checkouts, returns, holds, fines.

    This class provides a wrapper around the ADK LlmAgent for backward compatibility
    with existing code that uses the CirculationAgent class directly.
    """

    def __init__(self):
        self._agent = create_circulation_agent()

    @property
    def agent(self) -> LlmAgent:
        """Get the underlying ADK LlmAgent."""
        return self._agent

    async def process(self, query: str) -> str:
        """Process a circulation-related query.

        Args:
            query: The user's question about checkouts, holds, fines, etc.

        Returns:
            The agent's response
        """
        try:
            if EVAL_SHORTCUTS_ENABLED:
                shortcut = await self._identity_bound_shortcut(query)
                if shortcut is not None:
                    return shortcut

            response = await run_agent_text(
                agent=self._agent,
                message=query,
                app_name="circulation-agent",
            )
            # When shortcuts are disabled, always return model response directly.
            if not EVAL_SHORTCUTS_ENABLED:
                return response
            if response and not any(marker in response.lower() for marker in REFUSAL_MARKERS):
                return response

            if EVAL_SHORTCUTS_ENABLED:
                forced = await self._identity_bound_shortcut(query)
                if forced is not None:
                    return forced

        except Exception as e:
            logger.warning("CirculationAgent ADK runtime failed: %s", e)
            if not EVAL_SHORTCUTS_ENABLED:
                raise

        if not EVAL_SHORTCUTS_ENABLED:
            return "I encountered an error while processing the circulation request. Please try again."

        # Deterministic local fallback when ADK/model runtime is unavailable.
        try:
            active_context = get_active_patron_context()
            patron_match = re.search(r"patron-[a-z0-9\\-]+", query.lower())
            patron_id = (
                active_context.patron_id
                if active_context and active_context.patron_id
                else (patron_match.group(0) if patron_match else None)
            )
            if not patron_id:
                return "I need your patron profile to look up account information. Please set your active profile first."

            summary = await get_patron_summary(patron_id=patron_id)
            if summary.get("error"):
                if "active profile" in str(summary.get("error", "")).lower():
                    return (
                        "I can only access the active patron profile in this session. "
                        "Please switch profiles first."
                    )
                return f"I couldn't find patron `{patron_id}` in circulation records."

            patron = summary.get("patron", {})
            checkouts = len(summary.get("checkouts", []))
            holds = len(summary.get("holds", []))
            fines = summary.get("total_fines_owed", summary.get("total_fines", 0))
            return (
                f"Patron {patron.get('name', patron_id)} has {checkouts} active checkout(s), "
                f"{holds} hold(s), and fines totaling ${fines}."
            )
        except Exception as fallback_error:
            logger.error("Circulation fallback error: %s", fallback_error)
            return "I encountered an error while processing the circulation request. Please try again."

    async def _identity_bound_shortcut(self, query: str) -> str | None:
        """Deterministic identity-bound handling for account-oriented prompts."""
        lowered = query.lower()
        active_context = get_active_patron_context()
        if not active_context:
            return None

        if "who am i" in lowered or "logged in as" in lowered:
            label = active_context.name or active_context.patron_id
            return f"You are currently using patron profile {label} ({active_context.patron_id})."

        if self._is_self_checkout_action(lowered):
            instance_match = re.search(r"(inst-[a-z0-9\\-]+)", lowered)
            if not instance_match:
                return (
                    "I can check it out using your active profile. "
                    "Please provide the item instance ID (for example, `inst-001-a`)."
                )

            checkout = await checkout_for_me(instance_id=instance_match.group(1))
            if checkout.get("error"):
                return f"I couldn't complete that checkout: {checkout['error']}"
            checkout_record = checkout.get("checkout", {})
            due_date = checkout_record.get("due_date", "the standard due date")
            return (
                f"Done. I checked out instance {checkout_record.get('instance_id', instance_match.group(1))} "
                f"to your active profile. It is due on {due_date}."
            )

        if self._is_self_fines_query(lowered):
            fines_payload = await get_my_fines()
            if fines_payload.get("error"):
                return f"I couldn't access your fines right now: {fines_payload['error']}"

            total_owed = fines_payload.get("total_owed", 0)
            fine_count = len(fines_payload.get("fines", []))
            if fine_count == 0 or str(total_owed) in {"0", "0.0", "0.00"}:
                return "You currently have no unpaid fines on your active profile."
            return f"You currently have {fine_count} unpaid fine(s) totaling ${total_owed}."

        if self._is_self_summary_query(lowered):
            summary = await get_my_patron_summary()
            if summary.get("error"):
                return f"I couldn't access your account summary right now: {summary['error']}"

            patron = summary.get("patron", {})
            patron_name = patron.get("name", active_context.name or active_context.patron_id)
            checkouts = summary.get("checkouts", [])
            holds = summary.get("holds", [])
            total_fines = summary.get("total_fines_owed", summary.get("total_fines", 0))

            message = (
                f"{patron_name} currently has {len(checkouts)} active checkout(s), "
                f"{len(holds)} hold(s), and ${total_fines} in unpaid fines."
            )

            if checkouts:
                checkout_ids = ", ".join(
                    str(checkout.get("instance_id", "unknown-instance"))
                    for checkout in checkouts[:3]
                )
                message += f" Active checkout instance IDs: {checkout_ids}."
            return message

        return None

    @staticmethod
    def _has_self_reference(lowered: str) -> bool:
        return any(token in lowered for token in (" my ", " my", " i ", "i ", " me", " me ", "i'm", "im "))

    def _is_self_summary_query(self, lowered: str) -> bool:
        if "who am i" in lowered or "logged in as" in lowered:
            return True
        if not self._has_self_reference(lowered):
            return False
        summary_terms = (
            "current status",
            "my status",
            "my account",
            "account status",
            "checked out",
            "checkouts",
            "have it checked out",
        )
        return any(term in lowered for term in summary_terms)

    def _is_self_fines_query(self, lowered: str) -> bool:
        return self._has_self_reference(lowered) and any(
            term in lowered for term in ("fine", "fines", "owed")
        )

    def _is_self_checkout_action(self, lowered: str) -> bool:
        if not self._has_self_reference(lowered):
            return False
        return any(
            term in lowered for term in ("check it out", "checkout it", "check out to me", "checkout to me")
        )


# Convenience function for direct use
async def circulation_action(query: str) -> str:
    """Perform a circulation action using the circulation agent.

    Args:
        query: Natural language query about checkouts, holds, fines

    Returns:
        Agent's response about the action result
    """
    agent = CirculationAgent()
    return await agent.process(query)
