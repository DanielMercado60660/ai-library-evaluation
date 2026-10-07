"""Tests for outbound ILL requests (borrowing from other libraries)."""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import ILLRequestModel
from shared.constants import ILLRequestStatus


# =============================================================================
# Test: Create ILL Request
# =============================================================================

class TestCreateILLRequest:
    """Test creating outbound ILL requests."""

    @pytest.mark.asyncio
    async def test_create_request_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should create ILL request with valid data."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-001",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
                "notes": "Needed for dissertation research",
            },
        )

        assert response.status_code == 201
        data = response.json()

        # Verify response structure
        assert data["book_id"] == "book-ext-001"
        assert data["patron_id"] == "patron-001"
        assert data["source_library"] == "mastodon-institute"
        assert data["status"] == ILLRequestStatus.REQUESTED
        assert data["notes"] == "Needed for dissertation research"
        assert "id" in data
        assert "requested_at" in data

        # Verify saved to database
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == data["id"])
        )
        request = result.scalar_one()
        assert request.status == ILLRequestStatus.REQUESTED
        assert request.patron_id == "patron-001"

    @pytest.mark.asyncio
    async def test_create_request_generates_patron_reference(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should generate patron_reference from patron barcode."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-002",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )

        assert response.status_code == 201
        data = response.json()

        # patron_reference should be patron's barcode (HAN-P-XXX format)
        assert "patron_reference" in data
        assert data["patron_reference"].startswith("HAN-P-")

    @pytest.mark.asyncio
    async def test_create_request_without_notes(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should create request with notes=None."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-003",
                "patron_id": "patron-002",
                "source_library": "mastodon-institute",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["notes"] is None

    @pytest.mark.asyncio
    async def test_create_request_patron_not_found(self, client: AsyncClient):
        """Should return 404 if patron doesn't exist."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-004",
                "patron_id": "nonexistent-patron",
                "source_library": "mastodon-institute",
            },
        )

        assert response.status_code == 404
        assert "patron" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_request_invalid_source_library(self, client: AsyncClient):
        """Should return 400 if source_library is invalid."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-005",
                "patron_id": "patron-001",
                "source_library": "nonexistent-library",
            },
        )

        assert response.status_code == 400
        assert "library" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_request_book_available_locally(
        self, client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        """Reject ILL for an available local copy without calling a live catalog."""
        monkeypatch.setattr(
            "ill.routes.call_circulation",
            AsyncMock(return_value={"barcode": "HAN-P-001", "blocked": False}),
        )
        monkeypatch.setattr(
            "ill.routes.call_catalog",
            AsyncMock(side_effect=[
                {"id": "book-001", "title": "The Great Proboscis"},
                [{"id": "instance-001", "status": "available"}],
            ]),
        )
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-001",  # A book we have locally
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )

        assert response.status_code == 400
        error = response.json()["detail"]
        assert "available" in error.lower() or "local catalog" in error.lower()

    @pytest.mark.asyncio
    async def test_create_request_duplicate_active(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should prevent duplicate active ILL requests for same book/patron."""
        # Create first request
        await client.post(
            "/requests",
            json={
                "book_id": "book-ext-006",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )

        # Try to create duplicate
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-006",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )

        assert response.status_code == 400
        assert "already" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_create_request_missing_required_fields(self, client: AsyncClient):
        """Should return 422 for missing required fields."""
        # Missing book_id
        response = await client.post(
            "/requests",
            json={
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
            },
        )
        assert response.status_code == 422

        # Missing patron_id
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-007",
                "source_library": "mastodon-institute",
            },
        )
        assert response.status_code == 422

        # Missing source_library
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-008",
                "patron_id": "patron-001",
            },
        )
        assert response.status_code == 422


# =============================================================================
# Test: ILL Request Lifecycle
# =============================================================================

class TestILLRequestLifecycle:
    """Test status transitions through ILL request lifecycle."""

    @pytest.mark.asyncio
    async def test_mark_request_received_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_ill_request_shipped,
    ):
        """Should transition from 'shipped' to 'received' and set due date."""
        request_id = sample_ill_request_shipped.id

        response = await client.post(f"/requests/{request_id}/receive")

        assert response.status_code == 200
        data = response.json()

        # Verify status transition
        assert data["status"] == ILLRequestStatus.RECEIVED
        assert data["received_at"] is not None
        assert data["due_date"] is not None

        # Due date should be 28 days from receipt
        received_at = datetime.fromisoformat(data["received_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(data["due_date"].replace("Z", "+00:00"))
        days_difference = (due_date - received_at).days
        assert days_difference == 28

        # Verify database updated
        await db_session.refresh(sample_ill_request_shipped)
        assert sample_ill_request_shipped.status == ILLRequestStatus.RECEIVED
        assert sample_ill_request_shipped.received_at is not None
        assert sample_ill_request_shipped.due_date is not None

    @pytest.mark.asyncio
    async def test_mark_request_received_wrong_status(
        self, client: AsyncClient, sample_ill_request
    ):
        """Should fail if request is not in 'shipped' status."""
        request_id = sample_ill_request.id  # Status is 'requested', not 'shipped'

        response = await client.post(f"/requests/{request_id}/receive")

        assert response.status_code == 400
        assert "shipped" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_mark_request_received_not_found(self, client: AsyncClient):
        """Should return 404 for nonexistent request."""
        response = await client.post("/requests/nonexistent-id/receive")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_return_to_lender_success(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        sample_ill_request_received,
    ):
        """Should mark item as returned to lending library."""
        request_id = sample_ill_request_received.id

        response = await client.post(f"/requests/{request_id}/return")

        assert response.status_code == 200
        data = response.json()

        # Verify status transition
        assert data["status"] == ILLRequestStatus.RETURNED
        assert data["returned_to_lender_at"] is not None

        # Verify timestamp is recent
        returned_at = datetime.fromisoformat(
            data["returned_to_lender_at"].replace("Z", "+00:00")
        )
        now = datetime.now(UTC)
        # Ensure both datetimes are timezone-aware for comparison
        if returned_at.tzinfo is None:
            returned_at = returned_at.replace(tzinfo=UTC)
        assert (now - returned_at).total_seconds() < 60

        # Verify database updated
        await db_session.refresh(sample_ill_request_received)
        assert sample_ill_request_received.status == ILLRequestStatus.RETURNED

    @pytest.mark.asyncio
    async def test_return_to_lender_wrong_status(
        self, client: AsyncClient, sample_ill_request
    ):
        """Should fail if request is not in returnable status."""
        request_id = sample_ill_request.id  # Status is 'requested'

        response = await client.post(f"/requests/{request_id}/return")

        assert response.status_code == 400
        assert "status" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_receive_denied_request(
        self, client: AsyncClient, sample_ill_request_denied
    ):
        """Should not allow receiving a denied request."""
        request_id = sample_ill_request_denied.id

        response = await client.post(f"/requests/{request_id}/receive")

        assert response.status_code == 400
        assert "denied" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_return_before_receiving(
        self, client: AsyncClient, sample_ill_request_shipped
    ):
        """Should not allow returning before item is received."""
        request_id = sample_ill_request_shipped.id

        response = await client.post(f"/requests/{request_id}/return")

        assert response.status_code == 400


# =============================================================================
# Test: Query ILL Requests
# =============================================================================

class TestILLRequestQueries:
    """Test GET endpoints for ILL requests."""

    @pytest.mark.asyncio
    async def test_get_request_by_id(
        self, client: AsyncClient, sample_ill_request
    ):
        """Should retrieve ILL request by ID."""
        request_id = sample_ill_request.id

        response = await client.get(f"/requests/{request_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == request_id
        assert data["status"] == ILLRequestStatus.REQUESTED
        assert data["book_title"] == "Principles of Trunk Engineering"

    @pytest.mark.asyncio
    async def test_get_request_not_found(self, client: AsyncClient):
        """Should return 404 for nonexistent request."""
        response = await client.get("/requests/nonexistent-id")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_all_requests(
        self,
        client: AsyncClient,
        sample_ill_request,
        sample_ill_request_shipped,
        sample_ill_request_received,
    ):
        """Should list all ILL requests."""
        response = await client.get("/requests")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3

    @pytest.mark.asyncio
    async def test_list_requests_filter_by_patron(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ill_request_factory,
    ):
        """Should filter requests by patron_id."""
        # Create requests for different patrons
        await ill_request_factory(patron_id="patron-001")
        await ill_request_factory(patron_id="patron-001")
        await ill_request_factory(patron_id="patron-002")

        response = await client.get("/requests?patron_id=patron-001")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(r["patron_id"] == "patron-001" for r in data)

    @pytest.mark.asyncio
    async def test_list_requests_filter_by_status(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ill_request_factory,
    ):
        """Should filter requests by status."""
        # Create requests with different statuses
        await ill_request_factory(status=ILLRequestStatus.REQUESTED)
        await ill_request_factory(status=ILLRequestStatus.RECEIVED)
        await ill_request_factory(status=ILLRequestStatus.RETURNED)

        response = await client.get(f"/requests?status={ILLRequestStatus.RECEIVED.value}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["status"] == ILLRequestStatus.RECEIVED

    @pytest.mark.asyncio
    async def test_list_requests_filter_by_source_library(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ill_request_factory,
    ):
        """Should filter requests by source_library."""
        await ill_request_factory(source_library="mastodon-institute")
        await ill_request_factory(source_library="mammoth-valley")

        response = await client.get("/requests?source_library=mastodon-institute")

        assert response.status_code == 200
        data = response.json()
        assert all(r["source_library"] == "mastodon-institute" for r in data)

    @pytest.mark.asyncio
    async def test_list_requests_multiple_filters(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        ill_request_factory,
    ):
        """Should support multiple filter parameters."""
        await ill_request_factory(
            patron_id="patron-001",
            status=ILLRequestStatus.REQUESTED,
            source_library="mastodon-institute",
        )
        await ill_request_factory(
            patron_id="patron-001",
            status=ILLRequestStatus.RECEIVED,
            source_library="mastodon-institute",
        )
        await ill_request_factory(
            patron_id="patron-002",
            status=ILLRequestStatus.REQUESTED,
            source_library="mastodon-institute",
        )

        response = await client.get(
            f"/requests?patron_id=patron-001&status={ILLRequestStatus.REQUESTED.value}"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["patron_id"] == "patron-001"
        assert data[0]["status"] == ILLRequestStatus.REQUESTED

    @pytest.mark.asyncio
    async def test_list_requests_empty_result(self, client: AsyncClient):
        """Should return empty list when no requests match filters."""
        response = await client.get("/requests?patron_id=nonexistent-patron")

        assert response.status_code == 200
        data = response.json()
        assert data == []
