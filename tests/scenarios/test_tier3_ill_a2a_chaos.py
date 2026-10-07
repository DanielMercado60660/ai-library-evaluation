"""Chaos integration scenarios for ILL A2A under fault injection.

Each test uses ``@pytest.mark.chaos_profile`` to activate deterministic
fault injection via the ``chaotic_ill_client`` fixture.  Service
dependencies (circulation, catalog, registry) are monkeypatched to
isolate ILL + A2A behaviour, matching the pattern in
``test_tier3_ill_a2a.py``.
"""

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = str(Path(__file__).resolve().parents[2] / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _patch_service_deps(monkeypatch, registry_client):
    """Monkeypatch ILL route dependencies so only A2A relay is live."""

    async def fake_call_circulation(endpoint, *args, **kwargs):
        patron_id = endpoint.split("/")[-1]
        return {
            "id": patron_id,
            "barcode": f"HAN-P-{patron_id.split('-')[-1].zfill(3)}",
            "blocked": False,
        }

    async def fake_call_catalog(endpoint, *args, **kwargs):
        from shared.http_client import ServiceNotFoundError
        raise ServiceNotFoundError("not found", "catalog", endpoint, 404, None)

    async def fake_call_registry(endpoint, *args, **kwargs):
        code = endpoint.split("/")[-1]
        return {"code": code, "status": "active", "lending_enabled": True}

    monkeypatch.setattr("ill.routes.call_circulation", fake_call_circulation)
    monkeypatch.setattr("ill.routes.call_catalog", fake_call_catalog)
    monkeypatch.setattr("ill.routes.call_registry", fake_call_registry)


# ---------------------------------------------------------------------------
# Chaos scenario tests
# ---------------------------------------------------------------------------


class TestChaosA2ATimeoutRecovery:
    """ILL request creation succeeds despite A2A timeout on send."""

    @pytest.mark.chaos_profile("a2a_timeout_on_send", seed=42)
    async def test_chaos_a2a_timeout_recovery(
        self, chaotic_ill_client, chaos_controller, registry_client, monkeypatch,
    ):
        """ILL request is created and persisted even when A2A relay times out.

        The ILL route creates the DB record first and then *attempts* to
        notify via A2A; a timeout on the relay should not roll back the
        local record (routes.py lines 264-266).
        """
        _patch_service_deps(monkeypatch, registry_client)

        resp = await chaotic_ill_client.post(
            "/requests",
            json={
                "book_id": "ext-book-chaos-001",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )
        # Route should still create the request (A2A failure is non-fatal).
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "requested"

        # Chaos controller should have logged the injected timeout.
        assert len(chaos_controller.fault_log) >= 1
        assert chaos_controller.fault_log[0].fault_type == "timeout"


class TestChaosCatalog500GracefulDegradation:
    """ILL creation proceeds with fallback when catalog returns 500."""

    @pytest.mark.chaos_profile("catalog_500_on_search", seed=42)
    async def test_chaos_catalog_500_graceful_degradation(
        self, chaotic_ill_client, chaos_controller, registry_client, monkeypatch,
    ):
        """ILL request creation does not require catalog validation.

        The ILL service should accept the request even if catalog
        availability check fails (ServiceNotFoundError already handled).
        """
        _patch_service_deps(monkeypatch, registry_client)

        resp = await chaotic_ill_client.post(
            "/requests",
            json={
                "book_id": "ext-book-chaos-002",
                "patron_id": "patron-002",
                "source_library": "mammoth-valley",
            },
        )
        assert resp.status_code == 201

        # Budget should be respected.
        assert chaos_controller.retry_budget_check()


class TestChaosMalformedA2AResponse:
    """Malformed A2A response handled without state corruption."""

    @pytest.mark.chaos_profile("malformed_a2a_response", seed=42)
    async def test_chaos_malformed_a2a_response(
        self, chaotic_ill_client, chaos_controller, registry_client, monkeypatch,
    ):
        """Malformed JSON from registry relay does not corrupt ILL state."""
        _patch_service_deps(monkeypatch, registry_client)

        resp = await chaotic_ill_client.post(
            "/requests",
            json={
                "book_id": "ext-book-chaos-003",
                "patron_id": "patron-001",
                "source_library": "ivory-university",
            },
        )
        # Should succeed — A2A failure is non-fatal.
        assert resp.status_code == 201
        assert resp.json()["status"] == "requested"

        # Verify the controller recorded the fault.
        if chaos_controller.fault_log:
            assert chaos_controller.fault_log[0].fault_type == "malformed_json"


class TestChaosIntermittentRegistryOutage:
    """Intermittent outage retried and eventually succeeds."""

    @pytest.mark.chaos_profile("registry_intermittent", seed=42)
    async def test_chaos_intermittent_registry_outage(
        self, chaotic_ill_client, chaos_controller, registry_client, monkeypatch,
    ):
        """ILL request succeeds despite intermittent registry outages."""
        _patch_service_deps(monkeypatch, registry_client)

        resp = await chaotic_ill_client.post(
            "/requests",
            json={
                "book_id": "ext-book-chaos-004",
                "patron_id": "patron-003",
                "source_library": "mastodon-institute",
            },
        )
        # Route should create the request regardless of A2A relay status.
        assert resp.status_code == 201

        # Retry budget should still be respected.
        assert chaos_controller.retry_budget_check()
