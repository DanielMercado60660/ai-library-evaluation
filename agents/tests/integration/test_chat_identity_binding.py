"""Integration tests for /chat identity binding and session rotation."""

import pytest
from httpx import ASGITransport, AsyncClient

from agents.chat import ChatSession, ChatSessionManager


@pytest.fixture
def chat_app_with_identity(monkeypatch) -> tuple[object, ChatSessionManager]:
    """Provide API app wired with an isolated in-memory chat session manager."""
    import agents.api as api_module

    manager = ChatSessionManager(use_persistent_sessions=False)
    monkeypatch.setattr(api_module, "session_manager", manager)

    async def _fake_send_message(self: ChatSession, message: str) -> str:
        return f"ACK: {message}"

    monkeypatch.setattr(ChatSession, "send_message", _fake_send_message)
    return api_module.app, manager


class TestChatIdentityBinding:
    """Validate active patron context binding contract for /chat."""

    @pytest.mark.asyncio
    async def test_chat_binds_active_patron_context(
        self,
        chat_app_with_identity: tuple[object, ChatSessionManager],
    ) -> None:
        """POST /chat returns bound patron identity when active_patron is sent."""
        app, manager = chat_app_with_identity
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/chat",
                json={
                    "message": "Who am I?",
                    "active_patron": {
                        "id": "patron-001",
                        "name": "Trunsworth Greyvale",
                        "role": "patron",
                    },
                },
            )

        assert response.status_code == 200
        payload = response.json()
        assert payload["response"] == "ACK: Who am I?"
        assert payload["bound_patron_id"] == "patron-001"
        assert payload["session_rebound"] is False

        stored = await manager.get_session_async(payload["session_id"])
        assert stored is not None
        assert stored.bound_patron_id == "patron-001"
        assert stored.bound_patron_name == "Trunsworth Greyvale"
        assert stored.bound_patron_role == "patron"

    @pytest.mark.asyncio
    async def test_chat_rotates_session_on_patron_mismatch(
        self,
        chat_app_with_identity: tuple[object, ChatSessionManager],
    ) -> None:
        """Switching active patron for same session_id rotates backend session."""
        app, manager = chat_app_with_identity
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            first = await client.post(
                "/chat",
                json={
                    "message": "First message",
                    "active_patron": {
                        "id": "patron-001",
                        "name": "Trunsworth Greyvale",
                        "role": "patron",
                    },
                },
            )
            first_payload = first.json()

            second = await client.post(
                "/chat",
                json={
                    "message": "Second message",
                    "session_id": first_payload["session_id"],
                    "active_patron": {
                        "id": "patron-003",
                        "name": "Marcus Tuskwell",
                        "role": "staff",
                    },
                },
            )

        assert first.status_code == 200
        assert second.status_code == 200
        second_payload = second.json()
        assert second_payload["session_rebound"] is True
        assert second_payload["bound_patron_id"] == "patron-003"
        assert second_payload["session_id"] != first_payload["session_id"]

        rotated = await manager.get_session_async(second_payload["session_id"])
        assert rotated is not None
        assert rotated.bound_patron_id == "patron-003"

        original = manager.get_session(first_payload["session_id"])
        assert original is None

    @pytest.mark.asyncio
    async def test_chat_accepts_missing_active_patron(
        self,
        chat_app_with_identity: tuple[object, ChatSessionManager],
    ) -> None:
        """Legacy requests without active_patron remain backward compatible."""
        app, _ = chat_app_with_identity
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={"message": "Hello"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["response"] == "ACK: Hello"
        assert payload["bound_patron_id"] is None
        assert payload["session_rebound"] is False
