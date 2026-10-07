"""Compatibility helpers for executing ADK agents across runtime versions."""

from __future__ import annotations

import asyncio
import logging

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.config import AGENT_RESPONSE_TIMEOUT_SEC

logger = logging.getLogger(__name__)


def _extract_text_from_event(event) -> str:
    """Best-effort extraction of assistant text from an ADK event."""
    content = getattr(event, "content", None)
    if content is None:
        return ""

    parts = getattr(content, "parts", None) or []
    fragments: list[str] = []
    for part in parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text.strip():
            fragments.append(text.strip())

    return "\n".join(fragments).strip()


async def run_agent_text(
    *,
    agent: LlmAgent,
    message: str,
    user_id: str = "local-user",
    session_id: str = "default-session",
    app_name: str = "ai-library",
) -> str:
    """Run an ADK LlmAgent and return the final text response.

    Uses InMemoryRunner and `run_async` for compatibility with ADK >=1.23,
    where `LlmAgent.run(...)` is no longer available.

    Raises:
        TimeoutError: If the agent doesn't respond within AGENT_RESPONSE_TIMEOUT_SEC.
        RuntimeError: If the agent returns an error or no text response.
    """
    return await asyncio.wait_for(
        _run_agent_text_inner(
            agent=agent,
            message=message,
            user_id=user_id,
            session_id=session_id,
            app_name=app_name,
        ),
        timeout=AGENT_RESPONSE_TIMEOUT_SEC,
    )


async def _run_agent_text_inner(
    *,
    agent: LlmAgent,
    message: str,
    user_id: str,
    session_id: str,
    app_name: str,
) -> str:
    """Inner implementation without timeout wrapper."""
    runner = InMemoryRunner(agent=agent, app_name=app_name)
    runner.auto_create_session = True

    events = runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=types.Content(role="user", parts=[types.Part(text=message)]),
    )

    last_text = ""
    async for event in events:
        error_message = getattr(event, "error_message", None)
        if isinstance(error_message, str) and error_message.strip():
            raise RuntimeError(error_message)

        text = _extract_text_from_event(event)
        if text:
            last_text = text

        try:
            if event.is_final_response() and text:
                return text
        except Exception:
            # Some event implementations may not provide `is_final_response`.
            logger.debug("Event %s does not support is_final_response()", type(event).__name__)

    if last_text:
        return last_text

    raise RuntimeError("Agent returned no text response")
