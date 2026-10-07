"""Service trust enforcement tests.

Validates that ServiceAuthMiddleware rejects unauthenticated requests
and allows authenticated ones across all services.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from catalog.main import app as catalog_app
from circulation.main import app as circulation_app
from ill.main import app as ill_app
from registry.main import app as registry_app

VALID_TOKEN = "dev-token-ai-librarian"
INVALID_TOKEN = "wrong-token"
AUTH_HEADER = {"x-service-token": VALID_TOKEN}
BAD_HEADER = {"x-service-token": INVALID_TOKEN}


@pytest.fixture
def _no_auth_clients():
    """Marker fixture — tests in this module use explicit headers, not fixture defaults."""


class TestCatalogTrust:
    """Catalog service rejects unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_catalog_rejects_missing_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            resp = await client.get("/books")
            assert resp.status_code == 401
            assert resp.json()["detail"] == "Missing or invalid service token"

    @pytest.mark.asyncio
    async def test_catalog_accepts_valid_token(self, catalog_client):
        resp = await catalog_client.get("/books")
        assert resp.status_code == 200


class TestCirculationTrust:
    """Circulation service rejects unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_circulation_rejects_missing_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=circulation_app), base_url="http://test"
        ) as client:
            resp = await client.get("/patrons/nonexistent")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_circulation_accepts_valid_token(self, circulation_client):
        resp = await circulation_client.get("/patrons/nonexistent")
        # 404 is expected (patron doesn't exist), but NOT 401
        assert resp.status_code != 401


class TestILLTrust:
    """ILL service rejects unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_ill_rejects_missing_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=ill_app), base_url="http://test"
        ) as client:
            resp = await client.get("/requests")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_ill_accepts_valid_token(self, ill_client):
        resp = await ill_client.get("/requests")
        assert resp.status_code != 401


class TestRegistryTrust:
    """Registry service rejects unauthenticated requests."""

    @pytest.mark.asyncio
    async def test_registry_rejects_missing_token(self):
        async with AsyncClient(
            transport=ASGITransport(app=registry_app), base_url="http://test"
        ) as client:
            resp = await client.get("/libraries")
            assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_registry_accepts_valid_token(self, registry_client):
        resp = await registry_client.get("/libraries")
        assert resp.status_code != 401


class TestPublicPaths:
    """Health endpoints are always public (no token required)."""

    @pytest.mark.asyncio
    async def test_health_always_public(self):
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
                assert resp.status_code == 200, f"{name} /health should be public"


class TestInvalidToken:
    """Invalid tokens are rejected."""

    @pytest.mark.asyncio
    async def test_invalid_token_rejected(self):
        async with AsyncClient(
            transport=ASGITransport(app=catalog_app), base_url="http://test"
        ) as client:
            resp = await client.get("/books", headers=BAD_HEADER)
            assert resp.status_code == 401
