"""Tests for POST /admin/reset-and-seed endpoint."""

import pytest
from httpx import AsyncClient


class TestAdminResetAndSeed:
    """Validate the admin reset-and-seed endpoint."""

    @pytest.mark.asyncio
    async def test_returns_403_when_eval_mode_disabled(self, client: AsyncClient, monkeypatch):
        """Endpoint is gated behind EVAL_MODE env var."""
        monkeypatch.setenv("EVAL_MODE", "false")

        response = await client.post("/admin/reset-and-seed")

        assert response.status_code == 403
        assert "EVAL_MODE" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_seeds_books_and_patrons(self, client: AsyncClient, monkeypatch):
        """With EVAL_MODE=true, seeds catalog data from JSON files."""
        monkeypatch.setenv("EVAL_MODE", "true")

        response = await client.post("/admin/reset-and-seed")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "seeded"
        assert data["service"] == "catalog"
        assert data["records"] > 0

    @pytest.mark.asyncio
    async def test_seed_is_idempotent(self, client: AsyncClient, monkeypatch):
        """Running seed twice should produce same counts."""
        monkeypatch.setenv("EVAL_MODE", "true")

        resp1 = await client.post("/admin/reset-and-seed")
        assert resp1.status_code == 200
        resp2 = await client.post("/admin/reset-and-seed")
        assert resp2.status_code == 200

        assert resp1.json()["records"] == resp2.json()["records"]

    @pytest.mark.asyncio
    async def test_seeded_books_are_queryable(self, client: AsyncClient, monkeypatch):
        """After seeding, books should be retrievable via normal endpoints."""
        monkeypatch.setenv("EVAL_MODE", "true")

        seed_resp = await client.post("/admin/reset-and-seed")
        assert seed_resp.status_code == 200

        books_resp = await client.get("/books")
        assert books_resp.status_code == 200
        books = books_resp.json()
        assert len(books) > 0
