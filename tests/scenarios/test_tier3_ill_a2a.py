"""Tier 3 deterministic benchmark scenarios for ILL + A2A coordination."""

from datetime import datetime, UTC

import pytest


class TestTier3ILLA2AScenarios:
    """Cross-library ILL scenario using in-process relay and callback flow."""

    @pytest.mark.asyncio
    async def test_tier3_cross_library_happy_path(self, ill_client, registry_client, monkeypatch):
        """Request -> approve -> receive -> return -> ack closes lifecycle."""

        async def fake_call_circulation(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/patrons/"):
                patron_id = endpoint.split("/")[-1]
                return {
                    "id": patron_id,
                    "barcode": "HAN-P-900",
                    "blocked": False,
                }
            return {}

        async def fake_call_catalog(endpoint: str, *args, **kwargs):
            from shared.http_client import ServiceNotFoundError

            raise ServiceNotFoundError("not found", "catalog", endpoint, 404, None)

        async def fake_call_registry(endpoint: str, *args, **kwargs):
            if endpoint.startswith("/libraries/"):
                code = endpoint.split("/")[-1]
                return {
                    "code": code,
                    "status": "active",
                    "lending_enabled": True,
                }
            return {}

        async def fake_call_service(service, endpoint, method="GET", data=None, params=None, headers=None, timeout=10.0):
            assert service == "registry"
            if method == "POST" and endpoint == "/a2a/message/send":
                return (
                    await registry_client.post(
                        endpoint,
                        headers={"x-library-code": data["message"]["from_library"]},
                        json=data,
                    )
                ).json()
            raise AssertionError(f"Unsupported call_service in scenario: {service} {method} {endpoint}")

        monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
        monkeypatch.setattr("ill.routes.call_catalog", fake_call_catalog)
        monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)
        monkeypatch.setattr("ill.a2a_client.call_service", fake_call_service)

        create = await ill_client.post(
            "/requests",
            json={
                "book_id": "book-ext-tier3-001",
                "patron_id": "patron-tier3-001",
                "source_library": "mastodon-institute",
            },
        )
        assert create.status_code == 201
        request_id = create.json()["id"]

        request_inbox = await registry_client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert request_inbox.status_code == 200
        request_messages = request_inbox.json()["messages"]
        assert len(request_messages) == 1
        assert request_messages[0]["type"] == "loan_request"

        send_approval = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "loan_response",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"approved": True},
                }
            },
        )
        assert send_approval.status_code == 200

        inbound_for_hanno = await registry_client.get(
            "/a2a/messages/hanno-memorial",
            headers={"x-library-code": "hanno-memorial"},
        )
        assert inbound_for_hanno.status_code == 200
        approval_message = next(
            msg
            for msg in inbound_for_hanno.json()["messages"]
            if msg.get("type") == "loan_response" and msg.get("correlation_id") == request_id
        )

        apply_approval = await ill_client.post("/a2a/inbound", json={"message": approval_message})
        assert apply_approval.status_code == 200
        assert apply_approval.json()["updated_status"] == "shipped"

        receive = await ill_client.post(f"/requests/{request_id}/receive")
        assert receive.status_code == 200
        assert receive.json()["status"] == "received"

        returned = await ill_client.post(f"/requests/{request_id}/return")
        assert returned.status_code == 200
        assert returned.json()["status"] == "returned"
        assert returned.json()["returned_to_lender_at"] is not None

        return_notifications = await registry_client.get(
            "/a2a/messages/mastodon-institute",
            headers={"x-library-code": "mastodon-institute"},
        )
        assert return_notifications.status_code == 200
        return_messages = return_notifications.json()["messages"]
        assert len(return_messages) == 2
        latest = sorted(return_messages, key=lambda msg: msg["created_at"])[-1]
        assert latest["type"] == "item_returned"

        send_close_ack = await registry_client.post(
            "/a2a/message/send",
            headers={"x-library-code": "mastodon-institute"},
            json={
                "message": {
                    "type": "item_return_ack",
                    "from_library": "mastodon-institute",
                    "to_library": "hanno-memorial",
                    "correlation_id": request_id,
                    "payload": {"accepted": True, "received_at": datetime.now(UTC).isoformat()},
                }
            },
        )
        assert send_close_ack.status_code == 200

        ack_inbound = await registry_client.get(
            "/a2a/messages/hanno-memorial",
            headers={"x-library-code": "hanno-memorial"},
        )
        assert ack_inbound.status_code == 200
        close_message = next(
            msg
            for msg in ack_inbound.json()["messages"]
            if msg.get("type") == "item_return_ack" and msg.get("correlation_id") == request_id
        )

        close_response = await ill_client.post("/a2a/inbound", json={"message": close_message})
        assert close_response.status_code == 200
        assert close_response.json()["updated_status"] == "closed"

        final = await ill_client.get(f"/requests/{request_id}")
        assert final.status_code == 200
        assert final.json()["status"] == "closed"
        assert final.json()["closed_at"] is not None
