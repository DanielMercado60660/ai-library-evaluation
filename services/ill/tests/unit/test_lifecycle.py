"""
Test complete lifecycle workflows for ILL requests.

These tests verify the complete state transitions and workflows from start to finish:
- Outbound lifecycle: request → shipped → received → returned
- Inbound lifecycle: query → approve → ship → return
"""

from datetime import datetime, timedelta, UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import ILLRequestModel, InboundLoanModel
from shared.constants import ILLRequestStatus, InboundLoanStatus


# =============================================================================
# Test: Outbound Request Complete Lifecycle
# =============================================================================

class TestOutboundRequestLifecycle:
    """Test complete lifecycle of borrowing from another library."""

    @pytest.mark.asyncio
    async def test_complete_borrow_lifecycle(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test complete outbound ILL lifecycle:
        1. Create request (requested)
        2. External library ships (shipped)
        3. We receive item (received)
        4. Return to lender (returned)
        """
        # Step 1: Create ILL request
        create_response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-lifecycle-001",
                "patron_id": "patron-001",
                "source_library": "mastodon-institute",
                "notes": "Lifecycle test"
            }
        )
        assert create_response.status_code == 201
        request_data = create_response.json()
        request_id = request_data["id"]

        # Verify initial state
        assert request_data["status"] == ILLRequestStatus.REQUESTED
        assert request_data["received_at"] is None
        assert request_data["due_date"] is None

        # Step 2: Simulate external library shipping
        # (In production, this would be triggered by A2A protocol)
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        request = result.scalar_one()
        request.status = ILLRequestStatus.SHIPPED
        request.shipped_at = datetime.now(UTC)
        await db_session.commit()

        # Step 3: Mark as received
        receive_response = await client.post(f"/requests/{request_id}/receive")
        assert receive_response.status_code == 200
        received_data = receive_response.json()

        # Verify received state
        assert received_data["status"] == ILLRequestStatus.RECEIVED
        assert received_data["received_at"] is not None
        assert received_data["due_date"] is not None

        # Due date should be 28 days from receipt
        received_at = datetime.fromisoformat(received_data["received_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(received_data["due_date"].replace("Z", "+00:00"))
        days_diff = (due_date - received_at).days
        assert days_diff == 28

        # Step 4: Return to lender
        return_response = await client.post(f"/requests/{request_id}/return")
        assert return_response.status_code == 200
        returned_data = return_response.json()

        # Verify final state
        assert returned_data["status"] == ILLRequestStatus.RETURNED
        assert returned_data["returned_to_lender_at"] is not None

    @pytest.mark.asyncio
    async def test_denied_request_lifecycle(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test lifecycle when request is denied:
        1. Create request (requested)
        2. External library denies (denied)
        3. Cannot proceed with receive/return
        """
        # Step 1: Create ILL request
        create_response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-denied-001",
                "patron_id": "patron-002",
                "source_library": "mammoth-valley"
            }
        )
        assert create_response.status_code == 201
        request_id = create_response.json()["id"]

        # Step 2: Simulate denial by external library
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        request = result.scalar_one()
        request.status = ILLRequestStatus.DENIED
        request.denial_reason = "not_held"
        await db_session.commit()

        # Step 3: Verify cannot receive denied request
        receive_response = await client.post(f"/requests/{request_id}/receive")
        assert receive_response.status_code == 400
        assert "denied" in receive_response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_cannot_skip_lifecycle_steps(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Verify cannot skip required lifecycle steps."""
        # Create request in 'requested' state
        create_response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-skip-001",
                "patron_id": "patron-003",
                "source_library": "ivory-university"
            }
        )
        request_id = create_response.json()["id"]

        # Cannot receive without being shipped first
        receive_response = await client.post(f"/requests/{request_id}/receive")
        assert receive_response.status_code == 400
        assert "shipped" in receive_response.json()["detail"].lower()

        # Cannot return without being received first
        return_response = await client.post(f"/requests/{request_id}/return")
        assert return_response.status_code == 400

    @pytest.mark.asyncio
    async def test_query_filter_by_lifecycle_stage(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test querying requests at different lifecycle stages."""
        # Create multiple requests at different stages
        patron_id = "patron-lifecycle"

        # Create 3 requests
        for i in range(3):
            await client.post(
                "/requests",
                json={
                    "book_id": f"book-ext-stage-{i}",
                    "patron_id": patron_id,
                    "source_library": "mastodon-institute"
                }
            )

        # Get all patron's requests
        all_response = await client.get(f"/requests?patron_id={patron_id}")
        all_requests = all_response.json()
        assert len(all_requests) >= 3

        # All should be in 'requested' state initially
        requested_response = await client.get(
            f"/requests?patron_id={patron_id}&status={ILLRequestStatus.REQUESTED.value}"
        )
        requested = requested_response.json()
        assert len(requested) >= 3


# =============================================================================
# Test: Inbound Loan Complete Lifecycle
# =============================================================================

class TestInboundLoanLifecycle:
    """Test complete lifecycle of lending to another library."""

    @pytest.mark.asyncio
    async def test_complete_lending_lifecycle(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test complete inbound loan lifecycle:
        1. External library queries holdings (held, loanable)
        2. External library requests loan (approved)
        3. We ship item (active)
        4. They return item (returned)
        """
        isbn = "978-0-HANNO-0001"

        # Step 1: External library queries holdings
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn}
        )
        assert query_response.status_code == 200
        query_data = query_response.json()

        # Verify we have the book and it's loanable
        assert query_data["held"] is True
        assert query_data["loanable"] is True
        assert query_data["loan_period_days"] == 28

        # Step 2: External library requests loan
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn,
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-999"  # Their patron (opaque to us)
            }
        )
        assert loan_response.status_code == 200
        loan_data = loan_response.json()

        # Verify loan approved
        assert loan_data["approved"] is True
        assert loan_data["request_id"] is not None
        assert loan_data["loan_period_days"] == 28
        request_id = loan_data["request_id"]

        # Verify InboundLoan created in database
        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == request_id)
        )
        loan = result.scalar_one()
        assert loan.status == InboundLoanStatus.APPROVED
        assert loan.patron_reference == "MAS-P-999"  # Stored as opaque string
        assert loan.due_date is not None

        # Step 3: Simulate shipping
        loan.status = InboundLoanStatus.ACTIVE
        loan.shipped_at = datetime.now(UTC)
        await db_session.commit()

        # Step 4: They return the item
        return_response = await client.post(
            "/inbound/item-returned",
            json={"request_id": request_id}
        )
        assert return_response.status_code == 200
        return_data = return_response.json()

        # Verify returned state
        assert return_data["status"] == InboundLoanStatus.RETURNED
        assert return_data["returned_at"] is not None

    @pytest.mark.asyncio
    async def test_denied_loan_lifecycle(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test lifecycle when loan request is denied:
        1. Query shows book not held or unavailable
        2. Loan request denied with reason
        3. No InboundLoan record created
        """
        isbn_not_held = "978-0-MIT-9999"  # Not our book

        # Step 1: Query shows not held
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn_not_held}
        )
        query_data = query_response.json()
        assert query_data["held"] is False
        assert query_data["loanable"] is False

        # Step 2: Loan request denied
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn_not_held,
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-100"
            }
        )
        loan_data = loan_response.json()

        # Verify denial
        assert loan_data["approved"] is False
        assert loan_data["reason"] == "not_held"
        assert loan_data["request_id"] is None

        # Step 3: No InboundLoan created
        result = await db_session.execute(
            select(InboundLoanModel).where(
                InboundLoanModel.requesting_library == "mastodon-institute"
            )
        )
        loans = result.scalars().all()
        # Should not find loan for this denied request
        assert not any(loan.patron_reference == "MAS-P-100" for loan in loans)

    @pytest.mark.asyncio
    async def test_no_copies_available_lifecycle(
        self, client: AsyncClient
    ):
        """
        Test lifecycle when book is held but no copies available:
        1. Query shows held but not loanable
        2. Includes earliest_return_date
        3. Loan request denied with earliest_available
        """
        isbn_all_out = "978-0-HANNO-0002"  # All copies checked out

        # Step 1: Query shows held but not loanable
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn_all_out}
        )
        query_data = query_response.json()

        assert query_data["held"] is True
        assert query_data["available_copies"] == 0
        assert query_data["loanable"] is False
        assert query_data["earliest_return_date"] is not None

        # Step 2: Loan request denied
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn_all_out,
                "requesting_library": "mammoth-valley",
                "patron_reference": "MV-P-200"
            }
        )
        loan_data = loan_response.json()

        assert loan_data["approved"] is False
        assert loan_data["reason"] == "no_available_copies"
        assert loan_data["earliest_available"] is not None

    @pytest.mark.asyncio
    async def test_idempotent_return(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that marking already-returned loan is idempotent."""
        # Create and approve loan
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-300"
            }
        )
        request_id = loan_response.json()["request_id"]

        # Mark as active (shipped)
        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == request_id)
        )
        loan = result.scalar_one()
        loan.status = InboundLoanStatus.ACTIVE
        await db_session.commit()

        # First return - should succeed
        return1 = await client.post(
            "/inbound/item-returned",
            json={"request_id": request_id}
        )
        assert return1.status_code == 200
        assert return1.json()["status"] == InboundLoanStatus.RETURNED

        # Second return - should be idempotent
        return2 = await client.post(
            "/inbound/item-returned",
            json={"request_id": request_id}
        )
        assert return2.status_code == 200
        assert return2.json()["status"] == InboundLoanStatus.RETURNED


# =============================================================================
# Test: Cross-Lifecycle Integration
# =============================================================================

class TestCrossLifecycleIntegration:
    """Test interactions between outbound and inbound lifecycles."""

    @pytest.mark.asyncio
    async def test_simultaneous_borrow_and_lend(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Test that library can simultaneously:
        - Borrow books from other libraries (outbound)
        - Lend books to other libraries (inbound)
        """
        # Borrow from external library
        borrow_response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-simultaneous",
                "patron_id": "patron-both",
                "source_library": "mastodon-institute"
            }
        )
        assert borrow_response.status_code == 201
        borrow_id = borrow_response.json()["id"]

        # Lend to external library
        lend_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mammoth-valley",
                "patron_reference": "MV-P-BOTH"
            }
        )
        assert lend_response.status_code == 200
        lend_id = lend_response.json()["request_id"]

        # Verify both exist independently
        borrow_check = await client.get(f"/requests/{borrow_id}")
        assert borrow_check.status_code == 200

        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == lend_id)
        )
        assert result.scalar_one() is not None

    @pytest.mark.asyncio
    async def test_multiple_patrons_lifecycle(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that multiple patrons can have active ILL requests simultaneously."""
        patrons = ["patron-multi-1", "patron-multi-2", "patron-multi-3"]
        request_ids = []

        # Create ILL requests for multiple patrons
        for i, patron_id in enumerate(patrons):
            response = await client.post(
                "/requests",
                json={
                    "book_id": f"book-ext-multi-{i}",
                    "patron_id": patron_id,
                    "source_library": "mastodon-institute"
                }
            )
            assert response.status_code == 201
            request_ids.append(response.json()["id"])

        # Verify all requests exist
        for request_id in request_ids:
            check = await client.get(f"/requests/{request_id}")
            assert check.status_code == 200

        # Verify each patron can only see their own requests
        for patron_id in patrons:
            patron_requests = await client.get(f"/requests?patron_id={patron_id}")
            patron_data = patron_requests.json()
            assert len(patron_data) == 1
            assert patron_data[0]["patron_id"] == patron_id
