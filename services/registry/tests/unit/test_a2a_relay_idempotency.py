"""Additional relay tests for idempotent ack behavior."""

import pytest


class TestA2ARelayIdempotency:
    """Validate ack semantics remain idempotent and deterministic."""

    @pytest.mark.asyncio
    async def test_ack_is_idempotent_for_same_message(self, client, seeded_libraries):
        send_response = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "hanno-memorial"},
            json={
                "message": {
                    "type": "loan_request",
                    "from_library": "hanno-memorial",
                    "to_library": "mastodon-institute",
                    "payload": {"request_id": "ill-req-idempotent-001"},
                }
            },
        )
        assert send_response.status_code == 200
        message_id = send_response.json()["message_id"]

        first_ack = await client.post(
            f"/a2a/messages/{message_id}/ack",
            headers={"x-library-code": "mastodon-institute"},
            json={"library_code": "mastodon-institute"},
        )
        assert first_ack.status_code == 200
        assert first_ack.json()["acknowledged"] is True

        # Second ack should still succeed as a no-op idempotent acknowledgement.
        second_ack = await client.post(
            f"/a2a/messages/{message_id}/ack",
            headers={"x-library-code": "mastodon-institute"},
            json={"library_code": "mastodon-institute"},
        )
        assert second_ack.status_code == 200
        assert second_ack.json()["acknowledged"] is True

        pending_inbox = await client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert pending_inbox.status_code == 200
        assert pending_inbox.json()["total"] == 0

        full_inbox = await client.get(
            "/a2a/messages/mastodon-institute?include_acknowledged=true",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert full_inbox.status_code == 200
        assert full_inbox.json()["total"] == 1
        assert full_inbox.json()["messages"][0]["id"] == message_id

    @pytest.mark.asyncio
    async def test_duplicate_message_send_is_noop(self, client, seeded_libraries):
        """Sending the same message_id twice should only queue it once."""
        message_payload = {
            "message": {
                "id": "a2a-dedup-test-001",
                "type": "loan_request",
                "from_library": "hanno-memorial",
                "to_library": "mastodon-institute",
                "payload": {"request_id": "ill-req-dedup-001"},
            }
        }

        # First send — should be queued.
        r1 = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "hanno-memorial"},
            json=message_payload,
        )
        assert r1.status_code == 200
        assert r1.json()["status"] == "queued"

        # Second send with same id — duplicate no-op.
        r2 = await client.post(
            "/a2a/message/send",
            headers={"x-library-code": "hanno-memorial"},
            json=message_payload,
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "duplicate"

        # Inbox should only have 1 message.
        inbox = await client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert inbox.status_code == 200
        assert inbox.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_dedup_does_not_block_different_messages(self, client, seeded_libraries):
        """Different message IDs should both be queued."""
        for msg_id, req_id in [("a2a-unique-001", "ill-001"), ("a2a-unique-002", "ill-002")]:
            r = await client.post(
                "/a2a/message/send",
                headers={"x-library-code": "hanno-memorial"},
                json={
                    "message": {
                        "id": msg_id,
                        "type": "loan_request",
                        "from_library": "hanno-memorial",
                        "to_library": "mastodon-institute",
                        "payload": {"request_id": req_id},
                    }
                },
            )
            assert r.status_code == 200
            assert r.json()["status"] == "queued"

        inbox = await client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert inbox.status_code == 200
        assert inbox.json()["total"] == 2
