"""Tier 1 deterministic benchmark scenarios for catalog behavior."""

import pytest


class TestTier1CatalogScenarios:
    """Single-service synthetic catalog scenarios."""

    @pytest.mark.asyncio
    async def test_tier1_find_book_by_author(self, catalog_client):
        """Patron can find synthetic titles by author query."""
        response = await catalog_client.get("/books", params={"q": "Maren Greyhorn"})
        assert response.status_code == 200
        payload = response.json()

        assert payload["total"] >= 2
        titles = [book["title"] for book in payload["books"]]
        assert "The Tragedy of Lorde Tuskar" in titles
        assert "The Fall of Duchess Ivoryn" in titles

    @pytest.mark.asyncio
    async def test_tier1_get_book_detail_with_availability(self, catalog_client):
        """Book detail includes deterministic availability fields."""
        response = await catalog_client.get("/books/book-001")
        assert response.status_code == 200
        payload = response.json()

        assert payload["book"]["id"] == "book-001"
        assert payload["book"]["title"] == "The Tragedy of Lorde Tuskar"
        assert payload["total_copies"] == 2
        assert payload["available_copies"] == 1
