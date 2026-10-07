"""Fallback behavior tests for CatalogAgent query handling."""

import pytest

from agents.catalog_agent import CatalogAgent
import agents.catalog_agent as catalog_agent_module


@pytest.fixture
def fallback_agent(monkeypatch):
    """CatalogAgent instance that always uses fallback logic."""
    monkeypatch.setattr(catalog_agent_module, "EVAL_SHORTCUTS_ENABLED", True)

    async def failing_run_agent_text(**kwargs):  # noqa: ARG001
        raise RuntimeError("adk unavailable")

    monkeypatch.setattr(catalog_agent_module, "run_agent_text", failing_run_agent_text)

    agent = CatalogAgent.__new__(CatalogAgent)
    agent._agent = object()
    return agent


@pytest.mark.asyncio
async def test_catalog_fallback_uses_author_hint(monkeypatch, fallback_agent):
    """Natural-language author requests should use author filtering."""
    calls = []

    async def fake_search_books(
        query: str,
        genre=None,
        author=None,
        stratum=None,
        series=None,
        available_only=False,
        limit=10,
    ):
        calls.append({"query": query, "author": author, "limit": limit})
        if author == "Maren Greyhorn":
            return {
                "books": [{"title": "The Tragedy of Lorde Tuskar"}],
                "total": 2,
            }
        return {"books": [], "total": 0}

    monkeypatch.setattr(catalog_agent_module, "search_books", fake_search_books)

    response = await fallback_agent.process("Find books by Maren Greyhorn")

    assert calls, "Expected fallback to call search_books"
    assert calls[0]["author"] == "Maren Greyhorn"
    assert "I found 2 match(es)" in response
    assert "The Tragedy of Lorde Tuskar" in response


@pytest.mark.asyncio
async def test_catalog_fallback_normalizes_command_style_query(monkeypatch, fallback_agent):
    """Command-heavy prompts should retry with normalized query text."""
    calls = []

    async def fake_search_books(
        query: str,
        genre=None,
        author=None,
        stratum=None,
        series=None,
        available_only=False,
        limit=10,
    ):
        calls.append({"query": query, "author": author, "limit": limit})
        if query == "The Tragedy of Lorde Tuskar":
            return {
                "books": [{"title": "The Tragedy of Lorde Tuskar"}],
                "total": 1,
            }
        return {"books": [], "total": 0}

    monkeypatch.setattr(catalog_agent_module, "search_books", fake_search_books)

    response = await fallback_agent.process("Can you search for The Tragedy of Lorde Tuskar")

    assert any(call["query"] == "The Tragedy of Lorde Tuskar" for call in calls)
    assert "I found 1 match(es): The Tragedy of Lorde Tuskar" == response
