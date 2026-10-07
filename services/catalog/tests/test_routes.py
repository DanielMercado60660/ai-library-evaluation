"""Tests for catalog service routes."""

import pytest
from fastapi.testclient import TestClient

from catalog.main import app


@pytest.fixture
def client():
    """Create a test client for the catalog service."""
    return TestClient(app, headers={"x-service-token": "dev-token-ai-librarian"})


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        """Health endpoint should return 200 OK."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_service_info(self, client):
        """Health endpoint should return service information."""
        response = client.get("/health")
        data = response.json()

        assert data["status"] == "healthy"
        assert data["service"] == "catalog"
        assert "version" in data


class TestBooksEndpoint:
    """Tests for the books search endpoint."""

    def test_search_returns_200(self, client):
        """Search endpoint should return 200 OK."""
        response = client.get("/books")
        assert response.status_code == 200

    def test_search_returns_expected_structure(self, client):
        """Search should return books with pagination info."""
        response = client.get("/books")
        data = response.json()

        assert "books" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["books"], list)

    def test_search_with_query(self, client):
        """Search with a query parameter."""
        response = client.get("/books", params={"q": "test"})
        assert response.status_code == 200

    def test_search_with_limit(self, client):
        """Search with a custom limit."""
        response = client.get("/books", params={"limit": 5})
        data = response.json()

        assert data["limit"] == 5
        assert len(data["books"]) <= 5


class TestBookDetailsEndpoint:
    """Tests for the book details endpoint."""

    def test_nonexistent_book_returns_404(self, client):
        """Requesting a nonexistent book should return 404."""
        response = client.get("/books/nonexistent-id")
        assert response.status_code == 404
