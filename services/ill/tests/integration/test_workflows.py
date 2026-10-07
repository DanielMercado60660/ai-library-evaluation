"""
Integration tests for complete ILL workflows.

These tests verify end-to-end workflows including:
- Complete borrow workflow
- Complete lending workflow
- Error handling and edge cases
- Cross-service integration (future: with Catalog and Circulation)
"""

from datetime import datetime, timedelta, UTC

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import ILLRequestModel, InboundLoanModel
from shared.constants import ILLRequestStatus, InboundLoanStatus


# =============================================================================
# Test: Complete Borrow Workflow
# =============================================================================

class TestCompleteBorrowWorkflow:
    """Test complete workflow for borrowing books from other libraries."""

    @pytest.mark.asyncio
    async def test_successful_borrow_and_return_workflow(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        End-to-end borrow workflow:
        1. Patron requests external book
        2. External library approves and ships
        3. We receive and make available to patron
        4. Patron finishes, we return to lender
        5. Request closed
        """
        patron_id = "patron-workflow-001"
        book_id = "book-ext-workflow-001"

        # Step 1: Patron requests book via ILL
        create_response = await client.post(
            "/requests",
            json={
                "book_id": book_id,
                "patron_id": patron_id,
                "source_library": "mastodon-institute",
                "notes": "Research for thesis"
            }
        )
        assert create_response.status_code == 201
        request = create_response.json()
        request_id = request["id"]

        # Verify request created
        assert request["status"] == ILLRequestStatus.REQUESTED
        assert request["patron_id"] == patron_id
        assert request["notes"] == "Research for thesis"

        # Step 2: External library approves and ships
        # (In production: A2A protocol notification)
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one()
        ill_request.status = ILLRequestStatus.SHIPPED
        ill_request.shipped_at = datetime.now(UTC) - timedelta(days=2)
        await db_session.commit()

        # Step 3: We receive the book
        receive_response = await client.post(f"/requests/{request_id}/receive")
        assert receive_response.status_code == 200
        received = receive_response.json()

        assert received["status"] == ILLRequestStatus.RECEIVED
        assert received["received_at"] is not None
        assert received["due_date"] is not None

        # Due date should be set (28 days from receipt)
        due_date = datetime.fromisoformat(received["due_date"].replace("Z", "+00:00"))
        now = datetime.now(UTC)
        # Ensure both datetimes are timezone-aware
        if due_date.tzinfo is None:
            due_date = due_date.replace(tzinfo=UTC)
        days_until_due = (due_date - now).days
        assert 27 <= days_until_due <= 28  # Account for timing

        # TODO: In production, create checkout record for patron
        # For now, simulate patron usage by setting status to IN_USE
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one()
        ill_request.status = ILLRequestStatus.IN_USE
        await db_session.commit()

        # Step 4: Patron returns, we ship back to lender
        # First need to set back to RECEIVED to test return flow
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one()
        ill_request.status = ILLRequestStatus.RECEIVED
        await db_session.commit()

        return_response = await client.post(f"/requests/{request_id}/return")
        assert return_response.status_code == 200
        returned = return_response.json()

        assert returned["status"] == ILLRequestStatus.RETURNED
        assert returned["returned_to_lender_at"] is not None

        # Step 5: Verify complete request history
        final_check = await client.get(f"/requests/{request_id}")
        final = final_check.json()

        # Should have timestamps for entire journey
        assert final["requested_at"] is not None
        assert final["shipped_at"] is not None
        assert final["received_at"] is not None
        assert final["due_date"] is not None
        assert final["returned_to_lender_at"] is not None

    @pytest.mark.asyncio
    async def test_borrow_workflow_with_denial(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        Workflow when external library denies request:
        1. Patron requests book
        2. External library denies (not available)
        3. Request marked as denied
        4. Patron notified (future: via notification system)
        """
        # Step 1: Create request
        create_response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-denied-workflow",
                "patron_id": "patron-denial",
                "source_library": "mammoth-valley"
            }
        )
        request_id = create_response.json()["id"]

        # Step 2: External library denies
        result = await db_session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one()
        ill_request.status = ILLRequestStatus.DENIED
        ill_request.denial_reason = "no_available_copies"
        await db_session.commit()

        # Step 3: Verify denial status
        check = await client.get(f"/requests/{request_id}")
        denied = check.json()

        assert denied["status"] == ILLRequestStatus.DENIED
        assert denied["denial_reason"] == "no_available_copies"
        assert denied["received_at"] is None  # Never received

        # Step 4: Cannot proceed with receive/return
        receive_attempt = await client.post(f"/requests/{request_id}/receive")
        assert receive_attempt.status_code == 400

    @pytest.mark.asyncio
    async def test_multiple_patrons_concurrent_borrows(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that multiple patrons can have concurrent borrow workflows."""
        patrons = [
            ("patron-concurrent-1", "book-ext-concurrent-1"),
            ("patron-concurrent-2", "book-ext-concurrent-2"),
            ("patron-concurrent-3", "book-ext-concurrent-3"),
        ]

        request_ids = []

        # All patrons request books simultaneously
        for patron_id, book_id in patrons:
            response = await client.post(
                "/requests",
                json={
                    "book_id": book_id,
                    "patron_id": patron_id,
                    "source_library": "mastodon-institute"
                }
            )
            assert response.status_code == 201
            request_ids.append(response.json()["id"])

        # Verify all requests are independent
        assert len(set(request_ids)) == 3

        # Each patron should see only their request
        for (patron_id, _), request_id in zip(patrons, request_ids):
            patron_requests = await client.get(f"/requests?patron_id={patron_id}")
            data = patron_requests.json()
            assert len(data) == 1
            assert data[0]["id"] == request_id


# =============================================================================
# Test: Complete Lending Workflow
# =============================================================================

class TestCompleteLendingWorkflow:
    """Test complete workflow for lending books to other libraries."""

    @pytest.mark.asyncio
    async def test_successful_lending_workflow(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        End-to-end lending workflow:
        1. External library queries our holdings
        2. External library requests loan
        3. We approve and ship
        4. External library returns
        5. We restore item to available
        """
        isbn = "978-0-HANNO-0001"
        requesting_library = "mastodon-institute"
        patron_ref = "MAS-P-WORKFLOW"

        # Step 1: External library queries holdings
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn}
        )
        assert query_response.status_code == 200
        holdings = query_response.json()

        assert holdings["held"] is True
        assert holdings["loanable"] is True
        assert holdings["loan_period_days"] == 28

        # Step 2: External library requests loan
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn,
                "requesting_library": requesting_library,
                "patron_reference": patron_ref
            }
        )
        assert loan_response.status_code == 200
        loan = loan_response.json()

        assert loan["approved"] is True
        request_id = loan["request_id"]

        # Verify loan created
        result = await db_session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == request_id)
        )
        inbound_loan = result.scalar_one()
        assert inbound_loan.status == InboundLoanStatus.APPROVED
        assert inbound_loan.patron_reference == patron_ref  # Opaque storage
        assert inbound_loan.requesting_library == requesting_library

        # Step 3: We ship the item
        # (In production: Update catalog, mark instance as "ill_shipped")
        inbound_loan.status = InboundLoanStatus.ACTIVE
        inbound_loan.shipped_at = datetime.now(UTC) - timedelta(days=1)
        await db_session.commit()

        # Step 4: External library returns
        return_response = await client.post(
            "/inbound/item-returned",
            json={"request_id": request_id}
        )
        assert return_response.status_code == 200
        returned = return_response.json()

        assert returned["status"] == InboundLoanStatus.RETURNED
        assert returned["returned_at"] is not None

        # Step 5: Verify complete loan history
        await db_session.refresh(inbound_loan)
        assert inbound_loan.approved_at is not None
        assert inbound_loan.shipped_at is not None
        assert inbound_loan.returned_at is not None
        assert inbound_loan.due_date is not None

        # TODO: Verify instance status restored to "available" in catalog

    @pytest.mark.asyncio
    async def test_lending_workflow_book_not_held(
        self, client: AsyncClient
    ):
        """
        Workflow when we don't have the book:
        1. External library queries
        2. We respond not held
        3. External library cannot request loan
        """
        isbn_external = "978-0-MIT-9999"

        # Step 1: Query for book we don't have
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn_external}
        )
        holdings = query_response.json()

        assert holdings["held"] is False
        assert holdings["loanable"] is False
        assert holdings["total_copies"] == 0

        # Step 2: Attempt to request loan anyway
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn_external,
                "requesting_library": "mammoth-valley",
                "patron_reference": "MV-P-NOTHELD"
            }
        )
        loan = loan_response.json()

        assert loan["approved"] is False
        assert loan["reason"] == "not_held"
        assert loan["request_id"] is None

    @pytest.mark.asyncio
    async def test_lending_workflow_no_copies_available(
        self, client: AsyncClient
    ):
        """
        Workflow when book held but all copies checked out:
        1. Query shows held but not loanable
        2. Provides earliest return date
        3. Loan request denied with earliest_available
        """
        isbn_all_out = "978-0-HANNO-0002"

        # Step 1: Query shows no available copies
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": isbn_all_out}
        )
        holdings = query_response.json()

        assert holdings["held"] is True
        assert holdings["available_copies"] == 0
        assert holdings["loanable"] is False
        assert holdings["earliest_return_date"] is not None

        # Step 2: Loan request denied
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": isbn_all_out,
                "requesting_library": "ivory-university",
                "patron_reference": "IVY-P-UNAVAIL"
            }
        )
        loan = loan_response.json()

        assert loan["approved"] is False
        assert loan["reason"] == "no_available_copies"
        assert loan["earliest_available"] is not None


# =============================================================================
# Test: Cross-Service Integration (Future)
# =============================================================================

class TestCrossServiceIntegration:
    """
    Test integration with other services.
    
    NOTE: These tests document the expected integration patterns.
    Actual implementation requires Catalog and Circulation services to be running.
    """

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Catalog service integration")
    async def test_verify_book_not_in_local_catalog(
        self, client: AsyncClient
    ):
        """
        When creating ILL request, should verify book not in our catalog.
        
        Expected behavior:
        1. Query Catalog service for book_id
        2. If found and available, reject ILL request
        3. If not found, proceed with ILL request
        """
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Catalog service integration")
    async def test_query_holdings_from_catalog(
        self, client: AsyncClient
    ):
        """
        When responding to inbound query, should query actual catalog.
        
        Expected behavior:
        1. Search Catalog service by ISBN or title
        2. Get actual instance counts and availability
        3. Return aggregate data only (no patron info)
        """
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Catalog service integration")
    async def test_reserve_instance_for_inbound_loan(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        When approving inbound loan, should reserve instance.
        
        Expected behavior:
        1. Find available instance in Catalog
        2. Update instance status to "ill_shipped"
        3. Create InboundLoan with instance_id
        4. Instance not available for local checkouts
        """
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Circulation service integration")
    async def test_verify_patron_exists(
        self, client: AsyncClient
    ):
        """
        When creating ILL request, should verify patron in Circulation.
        
        Expected behavior:
        1. Query Circulation service for patron_id
        2. Verify patron is active and in good standing
        3. Get patron barcode for patron_reference
        4. If patron not found or blocked, reject request
        """
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires Circulation service integration")
    async def test_create_checkout_for_received_ill_item(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """
        When ILL item received, should create checkout for patron.
        
        Expected behavior:
        1. ILL item marked as received
        2. Create checkout in Circulation for patron
        3. Checkout uses ILL due date (28 days)
        4. Patron can check out the item
        """
        pass


# =============================================================================
# Test: Error Handling and Edge Cases
# =============================================================================

class TestWorkflowErrorHandling:
    """Test error handling in complete workflows."""

    @pytest.mark.asyncio
    async def test_duplicate_request_prevention(
        self, client: AsyncClient
    ):
        """Prevent duplicate active ILL requests for same book/patron."""
        patron_id = "patron-duplicate"
        book_id = "book-ext-duplicate"

        # Create first request
        response1 = await client.post(
            "/requests",
            json={
                "book_id": book_id,
                "patron_id": patron_id,
                "source_library": "mastodon-institute"
            }
        )
        assert response1.status_code == 201

        # Attempt duplicate
        response2 = await client.post(
            "/requests",
            json={
                "book_id": book_id,
                "patron_id": patron_id,
                "source_library": "mastodon-institute"
            }
        )
        assert response2.status_code == 400
        assert "already" in response2.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_state_transitions(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Test that invalid state transitions are prevented."""
        # Create request
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-invalid-state",
                "patron_id": "patron-state",
                "source_library": "mammoth-valley"
            }
        )
        request_id = response.json()["id"]

        # Cannot receive when status is 'requested' (not 'shipped')
        receive_attempt = await client.post(f"/requests/{request_id}/receive")
        assert receive_attempt.status_code == 400

        # Cannot return when status is 'requested' (not 'received')
        return_attempt = await client.post(f"/requests/{request_id}/return")
        assert return_attempt.status_code == 400

    @pytest.mark.asyncio
    async def test_data_isolation_in_workflow(
        self, client: AsyncClient
    ):
        """
        Verify data isolation throughout lending workflow.
        
        CRITICAL: External libraries should never see:
        - Our patron information
        - Checkout details
        - Individual instance details
        """
        # Query holdings - should only get aggregate data
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": "978-0-HANNO-0001"}
        )
        query_text = query_response.text.lower()

        # No patron info in query response
        assert "patron" not in query_text
        assert "han-p-" not in query_text
        assert "checkout" not in query_text

        # Loan request - should only get approval/denial
        loan_response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-ISOLATION"
            }
        )
        loan_text = loan_response.text.lower()

        # No patron info in loan response
        assert "han-p-" not in loan_text
        assert "checkout" not in loan_text

    @pytest.mark.asyncio
    async def test_workflow_with_invalid_library(
        self, client: AsyncClient
    ):
        """Test workflow with invalid source library."""
        response = await client.post(
            "/requests",
            json={
                "book_id": "book-ext-invalid-lib",
                "patron_id": "patron-001",
                "source_library": "nonexistent-library"
            }
        )
        assert response.status_code == 400
        assert "library" in response.json()["detail"].lower()
