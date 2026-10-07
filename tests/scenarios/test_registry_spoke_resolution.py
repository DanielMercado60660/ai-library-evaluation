"""Tests for registry spoke resolution and direct HTTP client.

Validates that:
- Registry returns catalog_url for spoke libraries
- call_url() correctly calls remote endpoints
- call_url() raises ServiceUnavailableError on connection failure
- call_remote_catalog() is a working convenience wrapper
"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from shared.http_client import (
    call_url,
    call_remote_catalog,
    ServiceNotFoundError,
    ServiceUnavailableError,
    ServiceBadRequestError,
)


class TestCallUrl:
    """Tests for the call_url() direct HTTP client."""

    @pytest.mark.asyncio
    async def test_call_url_get_success(self):
        """call_url returns JSON on successful GET."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"books": [{"id": "book-501"}], "total": 1}
        mock_response.raise_for_status = MagicMock()

        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await call_url("http://localhost:8011", "/books", params={"isbn": "978-0-GHLS-0501"})
            assert result["total"] == 1
            mock_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_url_post_success(self):
        """call_url sends JSON body on POST."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"held": True, "loanable": True}
        mock_response.raise_for_status = MagicMock()

        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await call_url(
                "http://localhost:8011",
                "/inbound/query",
                method="POST",
                data={"isbn": "978-0-GHLS-0501"},
            )
            assert result["held"] is True

    @pytest.mark.asyncio
    async def test_call_url_connection_error(self):
        """call_url raises ServiceUnavailableError on connection failure."""
        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ServiceUnavailableError, match="Cannot connect"):
                await call_url("http://localhost:9999", "/health")

    @pytest.mark.asyncio
    async def test_call_url_timeout(self):
        """call_url raises ServiceUnavailableError on timeout."""
        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("Timed out")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ServiceUnavailableError, match="timed out"):
                await call_url("http://localhost:8011", "/books", timeout=1.0)

    @pytest.mark.asyncio
    async def test_call_url_404(self):
        """call_url raises ServiceNotFoundError on 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = '{"detail": "Not found"}'
        mock_response.json.return_value = {"detail": "Not found"}

        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ServiceNotFoundError):
                await call_url("http://localhost:8011", "/books/nonexistent")

    @pytest.mark.asyncio
    async def test_call_url_400(self):
        """call_url raises ServiceBadRequestError on 400."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"detail": "Bad request"}'
        mock_response.json.return_value = {"detail": "Bad request"}

        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(ServiceBadRequestError):
                await call_url("http://localhost:8011", "/bad")

    @pytest.mark.asyncio
    async def test_call_url_strips_trailing_slash(self):
        """call_url handles base_url with trailing slash."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "healthy"}
        mock_response.raise_for_status = MagicMock()

        with patch("shared.http_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            await call_url("http://localhost:8011/", "/health")
            args = mock_client.get.call_args
            assert "http://localhost:8011/health" == args[0][0]


class TestCallRemoteCatalog:
    """Tests for call_remote_catalog convenience wrapper."""

    @pytest.mark.asyncio
    async def test_delegates_to_call_url(self):
        """call_remote_catalog delegates to call_url."""
        with patch("shared.http_client.call_url", new_callable=AsyncMock) as mock_call_url:
            mock_call_url.return_value = {"books": [], "total": 0}
            result = await call_remote_catalog(
                "http://localhost:8011",
                "/books",
                params={"isbn": "978-0-GHLS-0501"},
            )
            mock_call_url.assert_called_once_with(
                "http://localhost:8011", "/books", "GET", None, {"isbn": "978-0-GHLS-0501"}, 10.0
            )
            assert result["total"] == 0
