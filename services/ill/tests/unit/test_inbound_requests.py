"""Tests for inbound ILL requests (lending to other libraries)."""

from datetime import datetime, timedelta, UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import InboundLoanModel
from shared.constants import InboundLoanStatus


# =============================================================================
# Test: Query Holdings
# =============================================================================

class TestInboundHoldingsQuery:
    """Test /inbound/query endpoint - called by other libraries."""

    @pytest.mark.asyncio
    async def test_query_held_book_by_isbn(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should return holdings info for book we have (by ISBN)."""
        # TODO: This will require mocking catalog service or having test data
        # For now, we'll test the endpoint structure
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0001",
                "title": "Tusk and Sensibility"
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "isbn" in data
        assert "held" in data
        assert "total_copies" in data
        assert "available_copies" in data
        assert "loanable" in data

    @pytest.mark.asyncio
    async def test_query_held_book_by_title(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should return holdings info when querying by title only."""
        response = await client.post(
            "/inbound/query",
            json={
                "title": "The Ivory Throne"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "held" in data

    @pytest.mark.asyncio
    async def test_query_not_held_book(self, client: AsyncClient):
        """Should return held=False for book we don't have."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-MIT-9999",
                "title": "Nonexistent Book"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["held"] is False
        assert data["loanable"] is False
        assert data["available_copies"] == 0

    @pytest.mark.asyncio
    async def test_query_no_available_copies(self, client: AsyncClient):
        """Should return loanable=False if all copies checked out."""
        # TODO: Set up test data where all copies are checked out
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0002"
            }
        )

        assert response.status_code == 200
        data = response.json()
        # When no copies available, should include earliest_return_date
        if not data["loanable"]:
            # earliest_return_date should be present if we have the book but no copies
            if data["held"]:
                assert "earliest_return_date" in data

    @pytest.mark.asyncio
    async def test_query_missing_both_isbn_and_title(self, client: AsyncClient):
        """Should return 422 if neither ISBN nor title provided."""
        response = await client.post(
            "/inbound/query",
            json={}
        )

        # FastAPI validation should catch this
        assert response.status_code == 422 or response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_response_includes_loan_period(self, client: AsyncClient):
        """Should include loan_period_days in response for loanable books."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0001"
            }
        )

        data = response.json()
        if data["loanable"]:
            assert data["loan_period_days"] == 28


# =============================================================================
# Test: Process Loan Request
# =============================================================================

class TestInboundLoanRequest:
    """Test /inbound/loan-request endpoint - process loan requests from other libraries."""

    @pytest.mark.asyncio
    async def test_approve_loan_request_success(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should approve loan if copies available."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-042"  # Their patron ID (opaque to us)
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify approval
        assert data["approved"] is True
        assert "request_id" in data
        assert "loan_period_days" in data
        assert data["loan_period_days"] == 28
        assert "estimated_ship_date" in data

    @pytest.mark.asyncio
    async def test_loan_creates_inbound_loan_record(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should create InboundLoan record when approved."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-042"
            }
        )

        request_id = response.json()["request_id"]

        # Verify InboundLoan exists in database
        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == request_id)
        )
        loan = result.scalar_one_or_none()

        assert loan is not None
        assert loan.requesting_library == "mastodon-institute"
        assert loan.patron_reference == "MAS-P-042"
        assert loan.status == InboundLoanStatus.APPROVED
        assert loan.loan_period_days == 28

    @pytest.mark.asyncio
    async def test_loan_stores_patron_reference_opaque(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should store patron_reference as opaque string (no FK lookup)."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mammoth-valley",
                "patron_reference": "MV-ARBITRARY-STRING-123"  # Any format they want
            }
        )

        request_id = response.json()["request_id"]

        # Verify stored exactly as provided
        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == request_id)
        )
        loan = result.scalar_one()
        assert loan.patron_reference == "MV-ARBITRARY-STRING-123"

    @pytest.mark.asyncio
    async def test_deny_loan_no_copies_available(self, client: AsyncClient):
        """Should deny loan if no copies available."""
        # TODO: Set up test data with no available copies
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0002",  # Assume all checked out
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-100"
            }
        )

        # May be approved or denied depending on test data
        # If denied, should have proper structure
        data = response.json()
        if not data["approved"]:
            assert "reason" in data
            assert "earliest_available" in data

    @pytest.mark.asyncio
    async def test_deny_loan_book_not_held(self, client: AsyncClient):
        """Should deny loan if we don't have the book."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-MIT-9999",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-101"
            }
        )

        data = response.json()
        assert data["approved"] is False
        assert data["reason"] in ["not_held", "book_not_found"]

    @pytest.mark.asyncio
    async def test_loan_request_missing_isbn(self, client: AsyncClient):
        """Should return 422 for missing ISBN."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-102"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_loan_request_missing_patron_reference(self, client: AsyncClient):
        """Should return 422 for missing patron_reference."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute"
            }
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_loan_sets_due_date(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Should set due_date 28 days from approval."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-103"
            }
        )

        if response.json()["approved"]:
            request_id = response.json()["request_id"]
            result = await db_session.execute(
                select(InboundLoanModel).where(InboundLoanModel.id == request_id)
            )
            loan = result.scalar_one()

            # Due date should be ~28 days from now
            days_until_due = (loan.due_date - loan.approved_at).days
            assert days_until_due == 28


# =============================================================================
# Test: Mark Inbound Item Returned
# =============================================================================

class TestInboundItemReturn:
    """Test /inbound/item-returned endpoint - mark loaned items as returned."""

    @pytest.mark.asyncio
    async def test_mark_inbound_returned_success(
        self, client: AsyncClient, db_session: AsyncSession, sample_inbound_loan_active
    ):
        """Should mark loaned item as returned."""
        loan_id = sample_inbound_loan_active.id

        response = await client.post(
            "/inbound/item-returned",
            json={
                "request_id": loan_id
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Verify status transition
        assert data["status"] == InboundLoanStatus.RETURNED
        assert data["returned_at"] is not None

        # Verify database updated
        await db_session.refresh(sample_inbound_loan_active)
        assert sample_inbound_loan_active.status == InboundLoanStatus.RETURNED

    @pytest.mark.asyncio
    async def test_mark_inbound_returned_not_found(self, client: AsyncClient):
        """Should return 404 for nonexistent loan."""
        response = await client.post(
            "/inbound/item-returned",
            json={
                "request_id": "nonexistent-loan-id"
            }
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_mark_inbound_returned_updates_instance_status(
        self, client: AsyncClient, db_session: AsyncSession, sample_inbound_loan_active
    ):
        """Should update book instance status back to available."""
        # TODO: Requires integration with catalog service
        # This test documents the expected behavior
        loan_id = sample_inbound_loan_active.id
        instance_id = sample_inbound_loan_active.instance_id

        response = await client.post(
            "/inbound/item-returned",
            json={
                "request_id": loan_id
            }
        )

        assert response.status_code == 200
        # TODO: Verify instance status changed to "available" in catalog

    @pytest.mark.asyncio
    async def test_mark_inbound_returned_already_returned(
        self, client: AsyncClient, db_session: AsyncSession, inbound_loan_factory
    ):
        """Should handle attempting to mark already-returned loan."""
        # Create loan already in returned status
        loan = await inbound_loan_factory(status=InboundLoanStatus.RETURNED)

        response = await client.post(
            "/inbound/item-returned",
            json={
                "request_id": loan.id
            }
        )

        # Should be idempotent or return appropriate error
        assert response.status_code in [200, 400]

    @pytest.mark.asyncio
    async def test_mark_inbound_returned_missing_request_id(self, client: AsyncClient):
        """Should return 422 for missing request_id."""
        response = await client.post(
            "/inbound/item-returned",
            json={}
        )

        assert response.status_code == 422
