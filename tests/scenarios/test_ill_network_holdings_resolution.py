"""ILL federation scenarios proving local-miss/network-hit behavior.

Tests verify that ILL requests can target spoke libraries for books
not held by Hanno Memorial, using the federated seed manifest.
"""

import pytest


class TestILLNetworkHoldingsResolution:
    """ILL scenarios resolving books across the federated library network."""

    @pytest.mark.asyncio
    async def test_hanno_does_not_hold_spoke_book(self, catalog_client, spoke_holdings):
        """A book from mastodon-institute's partition returns 404 from Hanno's catalog."""
        mastodon_books = spoke_holdings["mastodon-institute"]
        spoke_book_id = mastodon_books[0]["id"]  # book-501

        resp = await catalog_client.get(f"/books/{spoke_book_id}")
        assert resp.status_code == 404, (
            f"Hanno should not hold {spoke_book_id}, got {resp.status_code}"
        )

    @pytest.mark.asyncio
    async def test_ill_request_for_spoke_book_succeeds(
        self, federated_ill_client, registry_client
    ):
        """ILL request for a book in mastodon-institute's holdings is created."""
        resp = await federated_ill_client.post(
            "/requests",
            json={
                "book_id": "book-501",
                "patron_id": "patron-fed-001",
                "source_library": "mastodon-institute",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_library"] == "mastodon-institute"
        assert data["status"] == "requested"

    @pytest.mark.asyncio
    async def test_ill_request_for_tusk_conservatory(
        self, federated_ill_client, registry_client
    ):
        """ILL request can now target tusk-conservatory as source library."""
        resp = await federated_ill_client.post(
            "/requests",
            json={
                "book_id": "book-151",
                "patron_id": "patron-fed-002",
                "source_library": "tusk-conservatory",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["source_library"] == "tusk-conservatory"

    @pytest.mark.asyncio
    async def test_holdings_query_resolves_spoke_isbn(
        self, federated_ill_client, spoke_holdings
    ):
        """Inbound holdings query for a spoke ISBN returns held=True."""
        mastodon_books = spoke_holdings["mastodon-institute"]
        isbn = mastodon_books[0]["isbn"]  # 978-0-GHLS-0501

        resp = await federated_ill_client.post(
            "/inbound/query",
            json={"isbn": isbn},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["held"] is True
        assert data["available_copies"] >= 1

    @pytest.mark.asyncio
    async def test_holdings_query_unknown_isbn_not_held(self, federated_ill_client):
        """Holdings query for ISBN not in any library returns held=False."""
        resp = await federated_ill_client.post(
            "/inbound/query",
            json={"isbn": "978-0-XXXX-9999"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["held"] is False

    @pytest.mark.asyncio
    async def test_cross_spoke_no_overlap(self, spoke_holdings):
        """A book in Ivory University is NOT in Mastodon's holdings."""
        ivory_ids = {b["id"] for b in spoke_holdings["ivory-university"]}
        mastodon_ids = {b["id"] for b in spoke_holdings["mastodon-institute"]}
        overlap = ivory_ids & mastodon_ids
        assert not overlap, f"Overlapping IDs: {overlap}"

    @pytest.mark.asyncio
    async def test_local_miss_remote_hit_full_lifecycle(
        self, federated_ill_client, registry_client
    ):
        """Full ILL lifecycle: catalog miss -> ILL request -> A2A notification."""
        # Step 1: ILL request for a book in mammoth-valley's holdings.
        resp = await federated_ill_client.post(
            "/requests",
            json={
                "book_id": "book-426",
                "patron_id": "patron-fed-003",
                "source_library": "mammoth-valley",
            },
        )
        assert resp.status_code == 201
        request_id = resp.json()["id"]

        # Step 2: Verify A2A notification was sent to mammoth-valley's inbox.
        inbox = await registry_client.get(
            "/a2a/messages/mammoth-valley",
            headers={"x-library-code": "mammoth-valley"},
        )
        assert inbox.status_code == 200
        messages = inbox.json()["messages"]
        assert any(
            m["payload"].get("request_id") == request_id
            or m["payload"].get("book_id") == "book-426"
            for m in messages
        ), "A2A notification for book-426 not found in mammoth-valley inbox"

    def test_spoke_specialization_genre_alignment(self, spoke_holdings):
        """Books assigned to each spoke have at least one genre matching specializations."""
        # Mapping of spoke codes to expected genre keywords.
        expected_genre_keywords = {
            "mastodon-institute": {"history", "technical", "science", "geology"},
            "mammoth-valley": {"tragedy", "fiction", "drama", "literary"},
            "ivory-university": {"philosophy", "ethics", "technical", "science"},
            "tusk-conservatory": {"poetry", "verse", "translated", "literary"},
        }
        for lib_code, books in spoke_holdings.items():
            keywords = expected_genre_keywords.get(lib_code, set())
            if not keywords:
                continue
            all_genres = set()
            for book in books:
                for genre in book.get("genres", []):
                    all_genres.add(genre.lower())
            # At least one genre keyword should appear across the spoke's books.
            found = any(
                any(kw in genre for kw in keywords)
                for genre in all_genres
            )
            assert found, (
                f"{lib_code}: no genre matches keywords {keywords}. "
                f"Genres found: {sorted(all_genres)[:10]}"
            )
