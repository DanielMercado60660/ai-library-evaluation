"""Live federation integration tests (v1.7).

These tests use real in-process catalog instances (one per spoke library),
each backed by its own in-memory SQLite database and seeded with that
spoke's books. ILL calls are intercepted and routed to the correct
spoke catalog via the live_federation_client fixture.
"""

import pytest


class TestSpokeDirectQuery:
    """Query spoke catalogs directly via in-process ASGI clients."""

    @pytest.mark.asyncio
    async def test_mastodon_catalog_returns_books(self, live_spoke_catalogs):
        """Mastodon catalog returns books from batch_07 + batch_03."""
        client = live_spoke_catalogs["mastodon-institute"]
        resp = await client.get("/books", params={"limit": 100})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 80
        # Spot-check: book-501 is from batch_07 (mastodon)
        ids = {b["id"] for b in data["books"]}
        assert "book-501" in ids

    @pytest.mark.asyncio
    async def test_mammoth_catalog_returns_books(self, live_spoke_catalogs):
        """Mammoth Valley catalog returns books from batch_06 + batch_10 + batch_08."""
        client = live_spoke_catalogs["mammoth-valley"]
        resp = await client.get("/books", params={"limit": 100})
        assert resp.status_code == 200
        data = resp.json()
        # total reflects all books even though limit caps page at 100
        assert data["total"] >= 165

    @pytest.mark.asyncio
    async def test_spoke_isbn_search(self, live_spoke_catalogs):
        """Search a spoke catalog by ISBN returns the correct book."""
        client = live_spoke_catalogs["mastodon-institute"]
        resp = await client.get("/books", params={"isbn": "978-0-GHLS-0501"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["books"][0]["title"] == "The Pachydon Expansion: 1720-1850"

    @pytest.mark.asyncio
    async def test_spoke_health_check(self, live_spoke_catalogs):
        """Spoke catalog health endpoint responds."""
        client = live_spoke_catalogs["ivory-university"]
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_spoke_book_not_found(self, live_spoke_catalogs):
        """Querying a book not in a spoke catalog returns empty results."""
        client = live_spoke_catalogs["tusk-conservatory"]
        resp = await client.get("/books", params={"isbn": "978-0-GHLS-0501"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0


class TestILLWithLiveSpokeVerification:
    """ILL request flow with live spoke catalog verification."""

    @pytest.mark.asyncio
    async def test_ill_request_spoke_holds_book(self, live_federation_client):
        """ILL request succeeds when spoke confirms it holds the book."""
        resp = await live_federation_client.post(
            "/requests",
            json={
                "book_id": "ext-mastodon-501",
                "isbn": "978-0-GHLS-0501",
                "patron_id": "patron-fed-001",
                "source_library": "mastodon-institute",
                "priority": "normal",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_library"] == "mastodon-institute"
        assert data["status"] == "requested"

    @pytest.mark.asyncio
    async def test_ill_request_spoke_does_not_hold_isbn(self, live_federation_client):
        """ILL request fails when spoke catalog says it doesn't hold the ISBN."""
        resp = await live_federation_client.post(
            "/requests",
            json={
                "book_id": "ext-tusk-fake-999",
                "isbn": "978-0-FAKE-9999",
                "patron_id": "patron-fed-002",
                "source_library": "tusk-conservatory",
                "priority": "normal",
            },
        )
        assert resp.status_code == 400
        assert "does not hold" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_cross_spoke_resolution(self, live_federation_client):
        """Mammoth Valley book requested via live catalog → confirms holdings."""
        # batch_06 book (mammoth-valley): book-426
        resp = await live_federation_client.post(
            "/requests",
            json={
                "book_id": "ext-mammoth-426",
                "isbn": "978-0-GHLS-0426",
                "patron_id": "patron-fed-003",
                "source_library": "mammoth-valley",
                "priority": "normal",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["source_library"] == "mammoth-valley"

    @pytest.mark.asyncio
    async def test_ill_request_no_isbn_skips_verification(self, live_federation_client):
        """ILL request without ISBN skips spoke verification (no catalog_url call)."""
        resp = await live_federation_client.post(
            "/requests",
            json={
                "book_id": "ext-ivory-unknown",
                "patron_id": "patron-fed-004",
                "source_library": "ivory-university",
                "priority": "normal",
            },
        )
        # Should succeed since there's no ISBN to verify
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_graceful_degradation_spoke_unreachable(
        self, ill_client, spoke_holdings, registry_client, monkeypatch
    ):
        """ILL proceeds with warning when spoke catalog is unreachable."""
        from shared.http_client import ServiceNotFoundError, ServiceUnavailableError

        async def fake_circ(endpoint, *a, **kw):
            return {"id": "p1", "barcode": "HAN-P-X", "blocked": False}

        async def fake_registry(endpoint, *a, **kw):
            if endpoint.startswith("/libraries/"):
                return {
                    "code": "mastodon-institute",
                    "status": "active",
                    "lending_enabled": True,
                    "catalog_url": "http://unreachable:9999",
                }
            return {}

        async def fake_remote_catalog(base_url, endpoint, **kw):
            raise ServiceUnavailableError(
                "Cannot connect", service=base_url, endpoint=endpoint
            )

        monkeypatch.setattr("ill.routes._is_known_local_book", lambda book_id: False)
        monkeypatch.setattr("ill.routes.call_circulation", fake_circ)
        monkeypatch.setattr("ill.routes.call_catalog", lambda *a, **kw: (_ for _ in ()).throw(
            ServiceNotFoundError("not local", "catalog", "", 404, None)
        ))
        monkeypatch.setattr("ill.routes.call_registry", fake_registry)
        monkeypatch.setattr("ill.routes.call_remote_catalog", fake_remote_catalog)
        monkeypatch.setattr("ill.a2a_client.call_service", lambda *a, **kw: (_ for _ in ()).throw(Exception("skip")))

        resp = await ill_client.post(
            "/requests",
            json={
                "book_id": "ext-graceful-001",
                "isbn": "978-0-GHLS-0501",
                "patron_id": "patron-graceful-001",
                "source_library": "mastodon-institute",
                "priority": "normal",
            },
        )
        # Should succeed — graceful degradation
        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_holdings_query_roundtrip(self, live_spoke_catalogs):
        """Query a spoke's /inbound/query endpoint via its live catalog."""
        # Note: /inbound/query is on ILL, not catalog. Here we query the
        # catalog /books endpoint directly as the spoke verification would.
        client = live_spoke_catalogs["tusk-conservatory"]
        # batch_02 book (tusk): book-151
        resp = await client.get("/books", params={"isbn": "978-0-GHLS-0151"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert data["books"][0]["id"] == "book-151"
