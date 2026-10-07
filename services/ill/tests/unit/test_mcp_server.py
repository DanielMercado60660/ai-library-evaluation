"""Tests for ILL MCP Server tools and resources.

These tests verify that the MCP server correctly:
- Exposes resources (pending queues, request details, audit trails)
- Executes tools (approve, deny, query audit)
- Handles edge cases and errors
"""

import json
from datetime import datetime, timedelta, UTC

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import ILLRequestModel, InboundLoanModel, ILLAuditTrail
from shared.constants import ILLRequestStatus, InboundLoanStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def pending_outbound_request(db_session):
    """Create a pending outbound ILL request for testing."""
    request = ILLRequestModel(
        id="ill-req-pending-001",
        book_id="book-ext-001",
        book_title="Test Book for Approval",
        isbn="978-0-TEST-0001",
        author="Test Author",
        patron_id="patron-001",
        patron_reference="HAN-P-001",
        source_library="mastodon-institute",
        status=ILLRequestStatus.PENDING_APPROVAL,
        priority="normal",
        patron_justification="Need for research",
        requested_at=datetime.now(UTC) - timedelta(days=2),
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def pending_inbound_loan(db_session):
    """Create a pending inbound loan for testing."""
    loan = InboundLoanModel(
        id="inbound-pending-001",
        instance_id="inst-001",
        book_id="book-001",
        requesting_library="mammoth-valley",
        patron_reference="MV-P-001",
        status=InboundLoanStatus.PENDING_APPROVAL,
        requested_at=datetime.now(UTC) - timedelta(days=1),
        due_date=datetime.now(UTC) + timedelta(days=28),
        loan_period_days=28,
    )
    db_session.add(loan)
    await db_session.commit()
    await db_session.refresh(loan)
    return loan


@pytest_asyncio.fixture
async def approved_request_with_audit(db_session):
    """Create an approved request with audit trail entries."""
    request = ILLRequestModel(
        id="ill-req-with-audit",
        book_id="book-ext-audit",
        book_title="Audited Book",
        patron_id="patron-audit",
        patron_reference="HAN-P-AUDIT",
        source_library="mastodon-institute",
        status=ILLRequestStatus.REQUESTED,
        approved_by="librarian-001",
        approved_at=datetime.now(UTC) - timedelta(hours=2),
        requested_at=datetime.now(UTC) - timedelta(days=1),
        loan_period_days=28,
    )
    db_session.add(request)

    # Add audit trail entries
    audit1 = ILLAuditTrail(
        id="audit-001",
        request_id="ill-req-with-audit",
        request_type="outbound",
        from_status="pending_approval",
        to_status="requested",
        changed_by="librarian-001",
        change_reason="Request approved",
        changed_at=datetime.now(UTC) - timedelta(hours=2),
    )
    db_session.add(audit1)

    await db_session.commit()
    await db_session.refresh(request)
    return request


# =============================================================================
# Tests for Approval Tool Functions
# =============================================================================

class TestApproveILLRequest:
    """Tests for the approve_ill_request MCP tool."""

    @pytest.mark.asyncio
    async def test_approve_pending_request_success(self, db_session, pending_outbound_request):
        """Approving a pending request should transition to REQUESTED status."""
        from ill.mcp_server import approve_ill_request

        result = await approve_ill_request(
            request_id=pending_outbound_request.id,
            librarian_id="test-agent",
            notes="Auto-approved by test"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["request_id"] == pending_outbound_request.id
        assert data["new_status"] == ILLRequestStatus.REQUESTED.value
        assert data["approved_by"] == "test-agent"

    @pytest.mark.asyncio
    async def test_approve_nonexistent_request_fails(self, db_session):
        """Approving a non-existent request should return an error."""
        from ill.mcp_server import approve_ill_request

        result = await approve_ill_request(
            request_id="nonexistent-id",
            librarian_id="test-agent",
            notes=""
        )

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_approve_already_approved_fails(self, db_session, approved_request_with_audit):
        """Approving an already approved request should fail."""
        from ill.mcp_server import approve_ill_request

        result = await approve_ill_request(
            request_id=approved_request_with_audit.id,
            librarian_id="test-agent",
            notes=""
        )

        data = json.loads(result)
        assert "error" in data
        assert "pending_approval" in data["error"].lower()


class TestDenyILLRequest:
    """Tests for the deny_ill_request MCP tool."""

    @pytest.mark.asyncio
    async def test_deny_pending_request_success(self, db_session, pending_outbound_request):
        """Denying a pending request should transition to DENIED status."""
        from ill.mcp_server import deny_ill_request

        result = await deny_ill_request(
            request_id=pending_outbound_request.id,
            librarian_id="test-agent",
            reason="Patron has outstanding fines"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["request_id"] == pending_outbound_request.id
        assert data["new_status"] == ILLRequestStatus.DENIED.value
        assert data["denied_by"] == "test-agent"
        assert data["denial_reason"] == "Patron has outstanding fines"

    @pytest.mark.asyncio
    async def test_deny_without_reason_fails(self, db_session, pending_outbound_request):
        """Denying without a reason should fail."""
        from ill.mcp_server import deny_ill_request

        result = await deny_ill_request(
            request_id=pending_outbound_request.id,
            librarian_id="test-agent",
            reason=""  # Empty reason
        )

        data = json.loads(result)
        assert "error" in data
        assert "reason" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_deny_nonexistent_request_fails(self, db_session):
        """Denying a non-existent request should return an error."""
        from ill.mcp_server import deny_ill_request

        result = await deny_ill_request(
            request_id="nonexistent-id",
            librarian_id="test-agent",
            reason="Test reason"
        )

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()


class TestApproveInboundLoan:
    """Tests for the approve_inbound_loan MCP tool."""

    @pytest.mark.asyncio
    async def test_approve_pending_loan_success(self, db_session, pending_inbound_loan):
        """Approving a pending inbound loan should transition to APPROVED."""
        from ill.mcp_server import approve_inbound_loan

        result = await approve_inbound_loan(
            loan_id=pending_inbound_loan.id,
            librarian_id="test-agent",
            notes="Instance available, approved"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["loan_id"] == pending_inbound_loan.id
        assert data["new_status"] == InboundLoanStatus.APPROVED.value
        assert data["approved_by"] == "test-agent"
        assert "due_date" in data

    @pytest.mark.asyncio
    async def test_approve_nonexistent_loan_fails(self, db_session):
        """Approving a non-existent loan should return an error."""
        from ill.mcp_server import approve_inbound_loan

        result = await approve_inbound_loan(
            loan_id="nonexistent-id",
            librarian_id="test-agent",
            notes=""
        )

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()


class TestDenyInboundLoan:
    """Tests for the deny_inbound_loan MCP tool."""

    @pytest.mark.asyncio
    async def test_deny_pending_loan_success(self, db_session, pending_inbound_loan):
        """Denying a pending inbound loan should transition to DENIED."""
        from ill.mcp_server import deny_inbound_loan

        result = await deny_inbound_loan(
            loan_id=pending_inbound_loan.id,
            librarian_id="test-agent",
            reason="Instance no longer available"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["loan_id"] == pending_inbound_loan.id
        assert data["new_status"] == InboundLoanStatus.DENIED.value
        assert data["denied_by"] == "test-agent"

    @pytest.mark.asyncio
    async def test_deny_without_reason_fails(self, db_session, pending_inbound_loan):
        """Denying without a reason should fail."""
        from ill.mcp_server import deny_inbound_loan

        result = await deny_inbound_loan(
            loan_id=pending_inbound_loan.id,
            librarian_id="test-agent",
            reason=""  # Empty reason
        )

        data = json.loads(result)
        assert "error" in data
        assert "reason" in data["error"].lower()


# =============================================================================
# Tests for Query Tools
# =============================================================================

class TestQueryAuditTrail:
    """Tests for the query_audit_trail MCP tool."""

    @pytest.mark.asyncio
    async def test_query_audit_by_request_id(self, db_session, approved_request_with_audit):
        """Querying audit trail by request_id should return entries."""
        from ill.mcp_server import query_audit_trail

        result = await query_audit_trail(
            request_id=approved_request_with_audit.id
        )

        data = json.loads(result)
        assert data["total_entries"] >= 1
        assert len(data["entries"]) >= 1
        assert data["entries"][0]["request_id"] == approved_request_with_audit.id

    @pytest.mark.asyncio
    async def test_query_audit_empty_result(self, db_session):
        """Querying audit trail for non-existent request returns empty."""
        from ill.mcp_server import query_audit_trail

        result = await query_audit_trail(
            request_id="nonexistent-request"
        )

        data = json.loads(result)
        assert data["total_entries"] == 0
        assert len(data["entries"]) == 0

    @pytest.mark.asyncio
    async def test_query_audit_with_date_filter(self, db_session, approved_request_with_audit):
        """Querying with date filters should work."""
        from ill.mcp_server import query_audit_trail

        # Query from a date in the future (should return nothing)
        future_date = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        result = await query_audit_trail(
            from_date=future_date
        )

        data = json.loads(result)
        assert data["total_entries"] == 0


class TestGetQueueStatistics:
    """Tests for the get_queue_statistics MCP tool."""

    @pytest.mark.asyncio
    async def test_queue_stats_with_pending_requests(self, db_session, pending_outbound_request, pending_inbound_loan):
        """Queue stats should count pending requests."""
        from ill.mcp_server import get_queue_statistics

        result = await get_queue_statistics()

        data = json.loads(result)
        assert data["outbound_pending"] >= 1
        assert data["inbound_pending"] >= 1
        assert data["total_pending"] >= 2

    @pytest.mark.asyncio
    async def test_queue_stats_empty_queues(self, db_session):
        """Queue stats with no pending requests."""
        from ill.mcp_server import get_queue_statistics

        result = await get_queue_statistics()

        data = json.loads(result)
        assert "outbound_pending" in data
        assert "inbound_pending" in data
        assert "total_pending" in data

    @pytest.mark.asyncio
    async def test_queue_stats_priority_breakdown(self, db_session, pending_outbound_request):
        """Queue stats should include priority breakdown."""
        from ill.mcp_server import get_queue_statistics

        result = await get_queue_statistics()

        data = json.loads(result)
        assert "outbound_by_priority" in data
        # The pending request has "normal" priority
        assert "normal" in data["outbound_by_priority"]


# =============================================================================
# Tests for Resource Access (via tools as resources aren't directly callable)
# =============================================================================

class TestPendingQueueResources:
    """Tests for pending queue resource data accuracy."""

    @pytest.mark.asyncio
    async def test_pending_outbound_includes_all_fields(self, db_session, pending_outbound_request):
        """Pending outbound queue should include enriched fields."""
        from ill.mcp_server import get_pending_outbound_queue

        result = await get_pending_outbound_queue()

        data = json.loads(result)
        assert data["total"] >= 1

        # Find our test request
        items = data["items"]
        test_item = next((i for i in items if i["id"] == pending_outbound_request.id), None)
        assert test_item is not None

        # Check required fields
        assert "book_id" in test_item
        assert "patron_id" in test_item
        assert "priority" in test_item
        assert "days_pending" in test_item
        assert test_item["days_pending"] >= 0

    @pytest.mark.asyncio
    async def test_pending_inbound_includes_all_fields(self, db_session, pending_inbound_loan):
        """Pending inbound queue should include required fields."""
        from ill.mcp_server import get_pending_inbound_queue

        result = await get_pending_inbound_queue()

        data = json.loads(result)
        assert data["total"] >= 1

        items = data["items"]
        test_item = next((i for i in items if i["id"] == pending_inbound_loan.id), None)
        assert test_item is not None

        # Check required fields
        assert "instance_id" in test_item
        assert "book_id" in test_item
        assert "requesting_library" in test_item
        assert "days_pending" in test_item


class TestRequestDetails:
    """Tests for individual request detail resources."""

    @pytest.mark.asyncio
    async def test_get_request_details_success(self, db_session, pending_outbound_request):
        """Getting request details should return all fields."""
        from ill.mcp_server import get_request_details

        result = await get_request_details(pending_outbound_request.id)

        data = json.loads(result)
        assert data["id"] == pending_outbound_request.id
        assert data["book_title"] == pending_outbound_request.book_title
        assert data["status"] == ILLRequestStatus.PENDING_APPROVAL.value

    @pytest.mark.asyncio
    async def test_get_request_details_not_found(self, db_session):
        """Getting non-existent request should return error."""
        from ill.mcp_server import get_request_details

        result = await get_request_details("nonexistent-id")

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_inbound_loan_details_success(self, db_session, pending_inbound_loan):
        """Getting inbound loan details should return all fields."""
        from ill.mcp_server import get_inbound_loan_details

        result = await get_inbound_loan_details(pending_inbound_loan.id)

        data = json.loads(result)
        assert data["id"] == pending_inbound_loan.id
        assert data["instance_id"] == pending_inbound_loan.instance_id
        assert data["status"] == InboundLoanStatus.PENDING_APPROVAL.value


class TestAuditTrailResource:
    """Tests for audit trail resource access."""

    @pytest.mark.asyncio
    async def test_get_audit_trail_for_request(self, db_session, approved_request_with_audit):
        """Getting audit trail should return all entries for a request."""
        from ill.mcp_server import get_audit_trail

        result = await get_audit_trail(approved_request_with_audit.id)

        data = json.loads(result)
        assert data["request_id"] == approved_request_with_audit.id
        assert data["total_entries"] >= 1
        assert len(data["entries"]) >= 1
