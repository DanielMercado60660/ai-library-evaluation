"""Unit tests for active-patron-aware circulation and ILL tools."""

import pytest

from agents.session.active_patron_context import bind_active_patron_context
from agents.tools import circulation_tools, ill_tools


class TestActivePatronCirculationTools:
    """Validate self-context helpers and cross-profile guards."""

    @pytest.mark.asyncio
    async def test_get_my_patron_summary_uses_active_context(self, monkeypatch):
        """Self summary tool should resolve patron id from contextvars."""

        async def _fake_get_patron_summary(patron_id: str) -> dict:
            return {"patron_id": patron_id, "ok": True}

        monkeypatch.setattr(circulation_tools, "get_patron_summary", _fake_get_patron_summary)

        with bind_active_patron_context("patron-003", name="Marcus Tuskwell", role="staff"):
            result = await circulation_tools.get_my_patron_summary()

        assert result == {"patron_id": "patron-003", "ok": True}

    @pytest.mark.asyncio
    async def test_get_my_patron_summary_errors_without_active_context(self):
        """Self summary tool should fail gracefully when no active patron exists."""
        with bind_active_patron_context(None):
            result = await circulation_tools.get_my_patron_summary()

        assert "error" in result
        assert "No active patron profile" in result["error"]

    @pytest.mark.asyncio
    async def test_checkout_item_blocks_cross_profile_with_active_context(self):
        """Explicit patron action should be blocked when patron mismatches context."""
        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            result = await circulation_tools.checkout_item(
                instance_id="inst-001-a",
                patron_id="patron-003",
            )

        assert "error" in result
        assert "bound to the active profile" in result["error"]


class TestActivePatronIllTools:
    """Validate ILL active-patron wrappers and policy checks."""

    @pytest.mark.asyncio
    async def test_create_ill_request_for_me_uses_active_context(self, monkeypatch):
        """Self ILL request helper should inject patron id from active context."""

        async def _fake_create_ill_request(
            book_id: str,
            patron_id: str,
            source_library: str,
            notes: str = "",
        ) -> dict:
            return {
                "book_id": book_id,
                "patron_id": patron_id,
                "source_library": source_library,
                "notes": notes,
            }

        monkeypatch.setattr(ill_tools, "create_ill_request", _fake_create_ill_request)

        with bind_active_patron_context("patron-008", name="Keeper Tuskmere", role="staff"):
            result = await ill_tools.create_ill_request_for_me(
                book_id="book-123",
                source_library="mammoth-valley",
                notes="Need for evaluation",
            )

        assert result["patron_id"] == "patron-008"
        assert result["book_id"] == "book-123"

    @pytest.mark.asyncio
    async def test_create_ill_request_for_me_errors_without_active_context(self):
        """Self ILL helper should fail gracefully when no active patron exists."""
        with bind_active_patron_context(None):
            result = await ill_tools.create_ill_request_for_me(
                book_id="book-123",
                source_library="mammoth-valley",
            )

        assert "error" in result
        assert "No active patron profile" in result["error"]

    @pytest.mark.asyncio
    async def test_create_ill_request_blocks_cross_profile_with_active_context(self):
        """Explicit patron ILL action should block cross-profile access."""
        with bind_active_patron_context("patron-001", name="Trunsworth Greyvale", role="patron"):
            result = await ill_tools.create_ill_request(
                book_id="book-ill-001",
                patron_id="patron-003",
                source_library="mastodon-institute",
                notes="test",
            )

        assert "error" in result
        assert "bound to the active profile" in result["error"]
