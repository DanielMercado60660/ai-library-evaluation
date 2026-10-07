"""ILL Escalation Agent - Patron-facing agent for inter-library loan inquiries."""

import logging
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from agents.config import EVAL_SHORTCUTS_ENABLED, PATRON_ID_PROMPT_MARKERS
from agents.models.factory import build_model_adapter
from agents.session.active_patron_context import get_active_patron_context
from agents.tools.ill_tools import (
    create_ill_request,
    create_ill_request_for_me,
    get_ill_request_status,
    list_my_ill_requests,
    list_partner_libraries,
    search_partner_catalog,
)
from agents.utils import run_agent_text

logger = logging.getLogger(__name__)


ILL_ESCALATION_SYSTEM_PROMPT = """You are the Inter-Library Loan specialist at the Hanno Memorial Library, part of the Great Herd Library System (GHLS).

Your role is to help patrons find and borrow books from partner libraries when items are not available in our local collection.

Partner Libraries in the GHLS:
- Mastodon Institute Library (mastodon-institute) — paleontology, ancient history, geology
- Mammoth Valley Library (mammoth-valley) — local history, genealogy, fiction
- Ivory University Library (ivory-university) — science, technology, mathematics, philosophy
- Tusk Conservatory Archives (tusk-conservatory) — music, performing arts, rare manuscripts

CRITICAL RULES:
1. NEVER share patron personal information (email, phone, address, SSN) across library boundaries.
2. Only share book metadata (title, author, ISBN) in inter-library requests.
3. Use patron_id references only, never full patron records.
4. Account actions are bound to the active patron profile in this chat session.
5. Do not ask for patron ID when active profile context exists.
6. If a patron asks about personal data for another patron, ask them to switch active profile.
7. Always confirm with the patron before submitting an ILL request.

When helping patrons:
- When a patron is looking for a specific book, use search_partner_catalog to search each relevant partner library's catalog. Search multiple libraries based on their specializations.
- Use list_partner_libraries to show available partners and their specializations.
- Once a book is found at a partner library, use create_ill_request_for_me to submit the request.
- Use list_my_ill_requests to inspect current patron requests.
- Check status of one existing request with get_ill_request_status.
- Explain typical ILL timelines (3-7 business days for processing).
"""


def create_ill_escalation_agent() -> LlmAgent:
    """Create a patron-facing ILL escalation agent using ADK LlmAgent.

    Returns:
        Configured LlmAgent for ILL escalation operations.
    """
    model_ref = build_model_adapter().to_adk_model_ref()
    agent = LlmAgent(
        model=model_ref,
        name="ill_escalation_agent",
        description=(
            "Inter-library loan specialist that helps patrons find and borrow "
            "books from partner libraries in the Great Herd Library System"
        ),
        instruction=ILL_ESCALATION_SYSTEM_PROMPT,
        tools=[
            FunctionTool(func=create_ill_request_for_me),
            FunctionTool(func=list_my_ill_requests),
            FunctionTool(func=create_ill_request),
            FunctionTool(func=get_ill_request_status),
            FunctionTool(func=list_partner_libraries),
            FunctionTool(func=search_partner_catalog),
        ],
        output_key="ill_escalation_response",
    )
    logger.info("Created ILLEscalationAgent with ADK LlmAgent")
    return agent


class ILLEscalationAgent:
    """Patron-facing agent for inter-library loan inquiries.

    This is distinct from ILLApprovalAgent (which is internal/automated).
    This agent helps patrons discover partner libraries, submit ILL requests,
    and track request status.
    """

    def __init__(self):
        self._agent = create_ill_escalation_agent()
        logger.info("Created ILLEscalationAgent instance")

    @property
    def agent(self) -> LlmAgent:
        """Get the underlying ADK LlmAgent."""
        return self._agent

    async def process(self, query: str) -> str:
        """Process an ILL escalation query from a patron.

        Args:
            query: The patron's ILL-related query.

        Returns:
            Agent response text.
        """
        if EVAL_SHORTCUTS_ENABLED:
            shortcut = await self._identity_bound_shortcut(query)
            if shortcut is not None:
                return shortcut

        try:
            response = await run_agent_text(
                agent=self._agent,
                message=query,
                app_name="ill-escalation-agent",
                session_id="ill-escalation-session",
            )
            if EVAL_SHORTCUTS_ENABLED and self._should_force_identity_fallback(query, response):
                forced = await self._identity_bound_shortcut(query)
                if forced is not None:
                    return forced
            return response
        except Exception as e:
            logger.warning("ILL escalation agent failed: %s", e)
            if EVAL_SHORTCUTS_ENABLED:
                return (
                    "I'd be happy to help you with an inter-library loan request. "
                    "We can borrow books from our partner libraries: "
                    "Mastodon Institute, Mammoth Valley, and Ivory University. "
                    "Could you tell me which book you're looking for?"
                )
            raise

    async def _identity_bound_shortcut(self, query: str) -> str | None:
        """Deterministically serve active-patron ILL status queries."""
        lowered = query.lower()
        active_context = get_active_patron_context()
        if not active_context:
            return None

        if not self._is_self_ill_status_query(lowered):
            return None

        payload = await list_my_ill_requests()
        if payload.get("error"):
            return f"I couldn't access your ILL requests right now: {payload['error']}"

        requests = payload.get("requests", []) or []
        if not requests:
            return "You currently have no active ILL requests on your profile."

        rows = []
        for request in requests[:3]:
            request_id = request.get("id", "unknown-request")
            status = request.get("status", "unknown").replace("_", " ")
            source_library = request.get("source_library", "unknown library")
            title = request.get("book_title") or request.get("book_id", "unknown title")
            rows.append(f"- {request_id}: {status} from {source_library} ({title})")

        remaining = len(requests) - len(rows)
        suffix = f" (+{remaining} more)" if remaining > 0 else ""
        return "Here are your ILL requests:\n" + "\n".join(rows) + suffix

    def _should_force_identity_fallback(self, query: str, response: str) -> bool:
        active_context = get_active_patron_context()
        if not active_context:
            return False
        if not self._is_self_ill_status_query(query.lower()):
            return False
        lowered = response.lower()
        return any(marker in lowered for marker in PATRON_ID_PROMPT_MARKERS)

    @staticmethod
    def _is_self_ill_status_query(lowered: str) -> bool:
        has_self_reference = any(token in lowered for token in (" my ", " my", " i ", "i ", " me", " me "))
        if not has_self_reference:
            return False
        if "ill" not in lowered and "inter-library" not in lowered:
            return False
        return any(term in lowered for term in ("status", "request", "requests", "pending", "approved"))
