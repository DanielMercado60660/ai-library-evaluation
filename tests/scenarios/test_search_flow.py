"""Scenario tests for synthetic catalog search flows."""

import json
from pathlib import Path

import pytest


class TestCatalogSearchScenarios:
    """Tier-1 style catalog search scenarios using in-process service fixtures."""

    @pytest.mark.asyncio
    async def test_search_by_author(self, catalog_client):
        """User searches for books by author name."""
        response = await catalog_client.get("/books", params={"q": "greyhorn"})
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1

        titles = [book["title"] for book in data["books"]]
        assert "The Tragedy of Lorde Tuskar" in titles

    @pytest.mark.asyncio
    async def test_search_multiple_results(self, catalog_client):
        """User searches and gets multiple results."""
        response = await catalog_client.get("/books", params={"q": "greyhorn"})
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 2

        titles = [book["title"] for book in data["books"]]
        assert "The Tragedy of Lorde Tuskar" in titles
        assert "The Fall of Duchess Ivoryn" in titles

    @pytest.mark.asyncio
    async def test_get_book_details(self, catalog_client):
        """User requests details about a specific book."""
        response = await catalog_client.get("/books/book-001")
        assert response.status_code == 200

        data = response.json()
        assert data["book"]["title"] == "The Tragedy of Lorde Tuskar"
        assert data["book"]["author"] == "Maren Greyhorn"
        assert data["total_copies"] >= 1
        assert "instances" in data

    @pytest.mark.asyncio
    async def test_book_availability_info(self, catalog_client):
        """Search results include availability information."""
        response = await catalog_client.get("/books", params={"q": "Tuskar"})
        assert response.status_code == 200

        data = response.json()
        assert len(data["books"]) >= 1

        book = data["books"][0]
        assert "total_copies" in book
        assert "available_copies" in book
        assert book["available_copies"] <= book["total_copies"]

    @pytest.mark.asyncio
    async def test_search_no_results(self, catalog_client):
        """User searches for something not in the catalog."""
        response = await catalog_client.get(
            "/books",
            params={"q": "xyznonexistentbook123"},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["total"] == 0
        assert len(data["books"]) == 0

    @pytest.mark.asyncio
    async def test_book_not_found(self, catalog_client):
        """User requests a book that doesn't exist."""
        response = await catalog_client.get("/books/nonexistent-book-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_search_pagination(self, catalog_client):
        """Search with pagination parameters."""
        response = await catalog_client.get(
            "/books",
            params={"limit": 5, "offset": 0},
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data["books"]) <= 5
        assert data["limit"] == 5
        assert data["offset"] == 0


class TestConversationScenarios:
    """Higher-level deterministic conversation scenarios."""

    @pytest.fixture
    def synthetic_catalog(self):
        """Load deterministic synthetic catalog fixture used by conversation tests."""
        data_path = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "hanno_memorial_library_catalog.json"
        )
        payload = json.loads(data_path.read_text(encoding="utf-8"))
        return payload["books"]

    def _mock_agent_find_books(self, catalog: list[dict], author_query: str) -> dict:
        """Deterministic mock: returns books by author substring."""
        matches = [
            book
            for book in catalog
            if author_query.lower() in str(book.get("author", "")).lower()
        ]
        return {
            "matches": matches,
            "response": (
                f"I found {len(matches)} result(s) by {author_query}: "
                + ", ".join(book.get("title", "Unknown") for book in matches[:5])
            ),
        }

    def _mock_agent_book_detail(self, catalog: list[dict], title_query: str) -> dict:
        """Deterministic mock: resolve one title and return summary payload."""
        match = next(
            (
                book
                for book in catalog
                if title_query.lower() in str(book.get("title", "")).lower()
            ),
            None,
        )
        if not match:
            return {"found": False, "response": "No matching title found."}
        return {
            "found": True,
            "book": match,
            "response": f"{match['title']} by {match['author']} is in the synthetic catalog.",
        }

    def test_patron_finds_book(self, synthetic_catalog):
        """
        Scenario: Patron asks about a book and gets helpful information.

        Steps:
        1. User: "Do you have any books by Maren Greyhorn?"
        2. Agent: Should search catalog and mention The Tragedy of Lorde Tuskar
        3. User: "Is it available?"
        4. Agent: Should provide availability info
        """
        step1 = self._mock_agent_find_books(synthetic_catalog, "Maren Greyhorn")
        assert step1["matches"], "Expected synthetic catalog to include Maren Greyhorn"
        assert any(
            book.get("title") == "The Tragedy of Lorde Tuskar"
            for book in step1["matches"]
        )

        step2 = self._mock_agent_book_detail(synthetic_catalog, "The Tragedy of Lorde Tuskar")
        assert step2["found"] is True
        assert step2["book"]["author"] == "Maren Greyhorn"
        assert "synthetic catalog" in step2["response"]

    def test_patron_explores_genres(self, synthetic_catalog):
        """
        Scenario: Patron explores books by genre.

        Steps:
        1. User: "What noble tragedies do you have?"
        2. Agent: Should list synthetic tragedies from the catalog
        3. User: "Tell me more about The Tragedy of Lorde Tuskar"
        4. Agent: Should provide book details
        """
        tragedies = [
            book
            for book in synthetic_catalog
            if any("traged" in genre.lower() for genre in book.get("genres", []))
        ]
        assert tragedies, "Expected at least one synthetic tragedy in seed catalog"
        assert any(book.get("title") == "The Tragedy of Lorde Tuskar" for book in tragedies)

        detail = self._mock_agent_book_detail(synthetic_catalog, "Lorde Tuskar")
        assert detail["found"] is True
        assert detail["book"]["title"] == "The Tragedy of Lorde Tuskar"
