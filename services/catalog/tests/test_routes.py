"""Tests for catalog service routes."""

import pytest
from httpx import AsyncClient

# Reuse the in-memory ASGI client from conftest.py.
pytestmark = pytest.mark.asyncio


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    async def test_health_returns_200(self, client: AsyncClient) -> None:
        """Health endpoint should return 200 OK."""
        response = await client.get("/health")
        assert response.status_code == 200

    async def test_health_returns_service_info(self, client: AsyncClient) -> None:
        """Health endpoint should return service information."""
        response = await client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "catalog"
        assert "version" in data


class TestBooksEndpoint:
    """Tests for the books search endpoint."""

    async def test_search_returns_200(self, client: AsyncClient) -> None:
        """Search endpoint should return 200 OK."""
        response = await client.get("/books")
        assert response.status_code == 200

    async def test_search_returns_expected_structure(self, client: AsyncClient) -> None:
        """Search should return books with pagination info."""
        response = await client.get("/books")
        data = response.json()

        assert "books" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["books"], list)

    async def test_search_with_query(self, client: AsyncClient) -> None:
        """Search with a query parameter."""
        response = await client.get("/books", params={"q": "test"})
        assert response.status_code == 200

    async def test_search_with_limit(self, client: AsyncClient) -> None:
        """Search with a custom limit."""
        response = await client.get("/books", params={"limit": 5})
        data = response.json()

        assert data["limit"] == 5
        assert len(data["books"]) <= 5


class TestBookDetailsEndpoint:
    """Tests for the book details endpoint."""

    async def test_nonexistent_book_returns_404(self, client: AsyncClient) -> None:
        """Requesting a nonexistent book should return 404."""
        response = await client.get("/books/nonexistent-id")
        assert response.status_code == 404
