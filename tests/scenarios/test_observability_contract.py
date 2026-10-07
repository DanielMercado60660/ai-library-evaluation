"""Observability contract tests.

Validates the structured log event schema, correlation ID middleware
behavior, and header propagation across all services.
"""

import json
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from shared.observability import StructuredLogEvent, RequestCorrelationMiddleware

from catalog.main import app as catalog_app
from circulation.main import app as circulation_app
from ill.main import app as ill_app
from registry.main import app as registry_app

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "golden"
AUTH_HEADERS = {"x-service-token": "dev-token-ai-librarian"}


class TestStructuredLogEventSchema:
    """Verify StructuredLogEvent Pydantic schema."""

    def test_structured_log_event_schema_valid(self):
        """Full StructuredLogEvent validates with all fields."""
        event = StructuredLogEvent(
            timestamp="2026-02-09T12:00:00Z",
            level="INFO",
            logger="test",
            message="hello",
            correlation_id="cid-123",
            run_id="run-001",
            service="catalog",
            extra={"key": "value"},
        )
        assert event.level == "INFO"
        assert event.correlation_id == "cid-123"

    def test_structured_log_event_minimal(self):
        """StructuredLogEvent validates with only required fields."""
        event = StructuredLogEvent(
            timestamp="2026-02-09T12:00:00Z",
            level="DEBUG",
            logger="test",
            message="minimal",
        )
        assert event.correlation_id is None
        assert event.run_id is None

    def test_golden_fixture_round_trip(self):
        """Golden fixture loads and validates through Pydantic."""
        raw = json.loads(
            (FIXTURES_DIR / "structured-log-event-v1.8.json").read_text(encoding="utf-8")
        )
        event = StructuredLogEvent.model_validate(raw)
        assert event.timestamp == "2026-02-09T12:00:00Z"
        assert event.service == "catalog"
        assert event.correlation_id == "abc123-def456"


class TestCorrelationMiddleware:
    """Verify RequestCorrelationMiddleware behavior."""

    @pytest.mark.asyncio
    async def test_correlation_middleware_generates_id(self):
        """Response includes X-Request-ID when none sent."""
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert "x-request-id" in resp.headers
            # Should be a valid UUID
            uuid.UUID(resp.headers["x-request-id"])

    @pytest.mark.asyncio
    async def test_correlation_middleware_echoes_provided_id(self):
        """Provided X-Request-ID is echoed back in the response."""
        custom_id = "my-custom-correlation-id"
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            resp = await client.get("/health", headers={"x-request-id": custom_id})
            assert resp.headers["x-request-id"] == custom_id

    @pytest.mark.asyncio
    async def test_all_services_return_correlation_header(self):
        """All 4 services return X-Request-ID on health endpoint."""
        apps = [
            ("catalog", catalog_app),
            ("circulation", circulation_app),
            ("ill", ill_app),
            ("registry", registry_app),
        ]
        for name, app in apps:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/health")
                assert "x-request-id" in resp.headers, f"{name} missing x-request-id"

    @pytest.mark.asyncio
    async def test_correlation_id_unique_per_request(self):
        """Two requests get different auto-generated IDs."""
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            r1 = await client.get("/health")
            r2 = await client.get("/health")
            assert r1.headers["x-request-id"] != r2.headers["x-request-id"]

    @pytest.mark.asyncio
    async def test_run_id_propagated_when_present(self):
        """X-Run-ID header is echoed when provided."""
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            resp = await client.get(
                "/health",
                headers={"x-run-id": "run-test-001"},
            )
            assert resp.headers.get("x-run-id") == "run-test-001"
