"""Tier 2 deterministic benchmark scenarios for circulation operations."""

import pytest


class TestTier2CirculationScenarios:
    """Multi-step circulation flows without external dependencies."""

    @pytest.mark.asyncio
    async def test_tier2_patron_summary_lookup(self, circulation_client):
        """Patron summary is available for seeded synthetic patron."""
        response = await circulation_client.get("/patrons/patron-001/summary")
        assert response.status_code == 200
        payload = response.json()

        assert payload["patron"]["id"] == "patron-001"
        assert payload["patron"]["barcode"] == "HAN-P-001"
        assert isinstance(payload["checkouts"], list)

    @pytest.mark.asyncio
    async def test_tier2_checkout_updates_state(self, circulation_client):
        """Checkout succeeds for available instance and then appears in patron summary."""
        checkout_response = await circulation_client.post(
            "/checkouts",
            json={
                "patron_id": "patron-001",
                "instance_id": "book-001-instance-001",
            },
        )
        assert checkout_response.status_code == 200
        checkout_payload = checkout_response.json()

        assert checkout_payload["checkout"]["patron_id"] == "patron-001"
        assert checkout_payload["checkout"]["instance_id"] == "book-001-instance-001"
        assert checkout_payload["checkout"]["status"] == "active"

        summary_response = await circulation_client.get("/patrons/patron-001/summary")
        assert summary_response.status_code == 200
        summary = summary_response.json()
        assert len(summary["checkouts"]) == 1
        assert summary["checkouts"][0]["id"] == checkout_payload["checkout"]["id"]
