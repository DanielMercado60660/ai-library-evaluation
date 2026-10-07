"""Unit tests for registry A2A relay endpoints."""

import pytest


class TestA2ARelayRoutes:
    """Validate relay send, inbox read, and ack behavior."""

    @pytest.mark.asyncio
    async def test_send_and_fetch_message(self, client, seeded_libraries):
        payload = {
            "message": {
                "type": "loan_request",
                "from_library": "hanno-memorial",
                "to_library": "mastodon-institute",
                "correlation_id": "ill-req-123",
                "payload": {"request_id": "ill-req-123"},
            }
        }
        send_response = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "hanno-memorial"},
            json=payload,
        )
        assert send_response.status_code == 200
        message_id = send_response.json()["message_id"]

        inbox = await client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert inbox.status_code == 200
        data = inbox.json()
        assert data["total"] == 1
        assert data["messages"][0]["id"] == message_id
        assert data["messages"][0]["correlation_id"] == "ill-req-123"

    @pytest.mark.asyncio
    async def test_acknowledge_hides_message(self, client, seeded_libraries):
        send_response = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "hanno-memorial"},
            json={
                "message": {
                    "type": "loan_request",
                    "from_library": "hanno-memorial",
                    "to_library": "mastodon-institute",
                    "payload": {"request_id": "ill-req-234"},
                }
            },
        )
        message_id = send_response.json()["message_id"]

        ack_response = await client.post(
            f"/a2a/messages/{message_id}/ack",
            headers={"x-library-code": "mastodon-institute"},
            json={"library_code": "mastodon-institute"},
        )
        assert ack_response.status_code == 200
        assert ack_response.json()["acknowledged"] is True

        inbox = await client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert inbox.status_code == 200
        assert inbox.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_sender_header_mismatch_rejected(self, client, seeded_libraries):
        response = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "wrong-library"},
            json={
                "message": {
                    "type": "loan_request",
                    "from_library": "hanno-memorial",
                    "to_library": "mastodon-institute",
                    "payload": {"request_id": "ill-req-345"},
                }
            },
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_ack_unknown_message_returns_404(self, client, seeded_libraries):
        response = await client.post(
            "/a2a/messages/does-not-exist/ack",
            headers={"x-library-code": "mastodon-institute"},
            json={"library_code": "mastodon-institute"},
        )
        assert response.status_code == 404
