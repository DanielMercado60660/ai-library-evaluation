"""Integration tests for Processor ↔ MCP tool interactions.

These tests verify that ILLApprovalProcessor and InboundLoanProcessor
correctly interact with MCP tools, process queues, and make decisions.
"""

import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, UTC

from agents.ill_approval_agent import (
    ILLApprovalProcessor,
    evaluate_request_for_approval,
)
from agents.inbound_loan_agent import (
    InboundLoanProcessor,
    evaluate_inbound_loan,
)


# =============================================================================
# ILL Approval Processor Tests
# =============================================================================


class TestILLApprovalProcessorMCP:
    """Tests for ILL Approval Processor MCP interactions."""

    @pytest.fixture
    def processor_with_mock_tools(self):
        """Create processor with mock MCP tools."""
        ill_tools = {
            "get_pending_outbound_queue": AsyncMock(return_value=json.dumps({
                "items": []
            })),
            "approve_ill_request": AsyncMock(return_value=json.dumps({
                "success": True,
                "request_id": "test-req-001",
            })),
            "deny_ill_request": AsyncMock(return_value=json.dumps({
                "success": True,
                "request_id": "test-req-001",
            })),
        }

        circulation_tools = {
            "check_patron_eligibility": AsyncMock(return_value=json.dumps({
                "eligible": True,
                "patron_id": "patron-001",
                "total_fines": 0,
                "issues": [],
            })),
        }

        return ILLApprovalProcessor(ill_tools, circulation_tools)

    @pytest.mark.asyncio
    async def test_fetches_pending_queue_from_mcp(self, processor_with_mock_tools):
        """Processor should call get_pending_outbound_queue MCP tool."""
        processor = processor_with_mock_tools

        # Set up mock to return specific queue
        processor.ill_tools["get_pending_outbound_queue"].return_value = json.dumps({
            "items": [
                {"id": "req-001", "patron_id": "p1", "book_title": "Test Book"},
                {"id": "req-002", "patron_id": "p2", "book_title": "Another Book"},
            ]
        })

        queue = await processor._get_pending_queue()

        # Verify MCP tool was called
        processor.ill_tools["get_pending_outbound_queue"].assert_called_once()

        # Verify response was parsed
        assert len(queue) == 2
        assert queue[0]["id"] == "req-001"

    @pytest.mark.asyncio
    async def test_checks_patron_eligibility_via_mcp(self, processor_with_mock_tools):
        """Processor should call check_patron_eligibility for each patron."""
        processor = processor_with_mock_tools

        eligibility = await processor._check_patron_eligibility("patron-001")

        # Verify MCP tool was called with patron ID
        processor.circulation_tools["check_patron_eligibility"].assert_called_once_with(
            "patron-001"
        )

        # Verify response
        assert eligibility["eligible"] is True
        assert eligibility["total_fines"] == 0

    @pytest.mark.asyncio
    async def test_approves_request_via_mcp(self, processor_with_mock_tools):
        """Processor should call approve_ill_request for approved requests."""
        processor = processor_with_mock_tools

        await processor._approve_request("req-001", "Good standing patron")

        # Verify MCP tool was called with correct params
        processor.ill_tools["approve_ill_request"].assert_called_once_with(
            request_id="req-001",
            librarian_id="ill-approval-agent",
            notes="Good standing patron",
        )

    @pytest.mark.asyncio
    async def test_denies_request_via_mcp(self, processor_with_mock_tools):
        """Processor should call deny_ill_request for denied requests."""
        processor = processor_with_mock_tools

        await processor._deny_request("req-001", "Patron blocked")

        # Verify MCP tool was called
        processor.ill_tools["deny_ill_request"].assert_called_once_with(
            request_id="req-001",
            librarian_id="ill-approval-agent",
            reason="Patron blocked",
        )

    @pytest.mark.asyncio
    async def test_full_queue_processing_approve_flow(self, processor_with_mock_tools):
        """Complete queue processing: fetch → evaluate → approve."""
        processor = processor_with_mock_tools

        # Set up mock queue with approvable request
        processor.ill_tools["get_pending_outbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "req-approve-001",
                "patron_id": "good-patron",
                "book_title": "Eligible Book",
                "library_context": {"fulfillment_rate": 0.92},
            }]
        })

        # Patron is eligible (low fines)
        processor.circulation_tools["check_patron_eligibility"].return_value = json.dumps({
            "eligible": True,
            "total_fines": 2.00,
            "issues": [],
        })

        results = await processor.process_pending_queue()

        # Verify results
        assert results["total_processed"] == 1
        assert len(results["approved"]) == 1
        assert len(results["denied"]) == 0
        assert len(results["skipped"]) == 0

        # Verify approve was called
        processor.ill_tools["approve_ill_request"].assert_called_once()

    @pytest.mark.asyncio
    async def test_full_queue_processing_deny_flow(self, processor_with_mock_tools):
        """Complete queue processing: fetch → evaluate → deny."""
        processor = processor_with_mock_tools

        # Set up mock queue
        processor.ill_tools["get_pending_outbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "req-deny-001",
                "patron_id": "blocked-patron",
                "book_title": "Some Book",
            }]
        })

        # Patron is blocked
        processor.circulation_tools["check_patron_eligibility"].return_value = json.dumps({
            "eligible": False,
            "total_fines": 15.00,
            "issues": [{"type": "blocked", "reason": "Account blocked"}],
        })

        results = await processor.process_pending_queue()

        # Verify results
        assert results["total_processed"] == 1
        assert len(results["approved"]) == 0
        assert len(results["denied"]) == 1
        assert "blocked" in results["denied"][0]["reason"].lower()

        # Verify deny was called
        processor.ill_tools["deny_ill_request"].assert_called_once()

    @pytest.mark.asyncio
    async def test_full_queue_processing_mixed(self, processor_with_mock_tools):
        """Process queue with mixed decisions."""
        processor = processor_with_mock_tools

        # Queue with multiple requests
        processor.ill_tools["get_pending_outbound_queue"].return_value = json.dumps({
            "items": [
                {"id": "req-1", "patron_id": "good-patron", "library_context": {"fulfillment_rate": 0.90}},
                {"id": "req-2", "patron_id": "blocked-patron", "library_context": {}},
                {"id": "req-3", "patron_id": "fines-patron", "library_context": {"fulfillment_rate": 0.80}},
            ]
        })

        # Different eligibility responses per patron
        async def eligibility_by_patron(patron_id):
            responses = {
                "good-patron": {"eligible": True, "total_fines": 0, "issues": []},
                "blocked-patron": {"eligible": False, "total_fines": 12, "issues": [{"type": "blocked"}]},
                "fines-patron": {"eligible": True, "total_fines": 7.50, "issues": []},
            }
            return json.dumps(responses.get(patron_id, {"eligible": True, "total_fines": 0, "issues": []}))

        processor.circulation_tools["check_patron_eligibility"].side_effect = eligibility_by_patron

        results = await processor.process_pending_queue()

        # Verify counts
        assert results["total_processed"] == 3
        assert len(results["approved"]) == 1  # good-patron
        assert len(results["denied"]) == 1    # blocked-patron
        assert len(results["skipped"]) == 1   # fines-patron (moderate fines)

    @pytest.mark.asyncio
    async def test_handles_mcp_tool_error(self, processor_with_mock_tools):
        """Processor should handle MCP tool errors gracefully."""
        processor = processor_with_mock_tools

        # Queue fetch fails - processor catches this and returns empty queue
        processor.ill_tools["get_pending_outbound_queue"].side_effect = Exception("Connection failed")

        results = await processor.process_pending_queue()

        # When queue fetch fails, processor returns empty results (no items processed)
        assert results["total_processed"] == 0
        assert len(results["approved"]) == 0
        assert len(results["denied"]) == 0

    @pytest.mark.asyncio
    async def test_handles_eligibility_check_error(self, processor_with_mock_tools):
        """Processor should handle patron eligibility check errors."""
        processor = processor_with_mock_tools

        processor.ill_tools["get_pending_outbound_queue"].return_value = json.dumps({
            "items": [{"id": "req-1", "patron_id": "error-patron"}]
        })

        # Eligibility check fails - but processor should continue with default
        processor.circulation_tools["check_patron_eligibility"].side_effect = Exception("DB error")

        results = await processor.process_pending_queue()

        # Should still process (with fallback eligibility)
        assert results["total_processed"] == 1


# =============================================================================
# Inbound Loan Processor Tests
# =============================================================================


class TestInboundLoanProcessorMCP:
    """Tests for Inbound Loan Processor MCP interactions."""

    @pytest.fixture
    def inbound_processor_with_mock_tools(self):
        """Create processor with mock MCP tools.

        Note: Tools that have their results parsed by the processor return JSON strings.
        Tools whose results are used directly return dicts.
        """
        ill_tools = {
            # Returns JSON string - parsed by _get_pending_queue
            "get_pending_inbound_queue": AsyncMock(return_value=json.dumps({
                "items": []
            })),
            # Returns dict - used directly by _approve_loan
            "approve_inbound_loan": AsyncMock(return_value={"success": True}),
            # Returns dict - used directly by _deny_loan
            "deny_inbound_loan": AsyncMock(return_value={"success": True}),
        }

        catalog_tools = {
            # Returns JSON string - parsed by _check_availability
            "check_availability": AsyncMock(return_value=json.dumps({
                "is_available": True,
                "total_copies": 3,
                "available_copies": 2,
            })),
            # Returns dict - used directly by _reserve_instance, result.get() is called
            "reserve_instance": AsyncMock(return_value={"success": True}),
        }

        return InboundLoanProcessor(ill_tools, catalog_tools)

    @pytest.mark.asyncio
    async def test_fetches_inbound_queue_from_mcp(self, inbound_processor_with_mock_tools):
        """Processor should call get_pending_inbound_queue MCP tool."""
        processor = inbound_processor_with_mock_tools

        # Set up mock queue
        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [
                {"id": "loan-001", "instance_id": "inst-001", "requesting_library": "mastodon"},
            ]
        })

        queue = await processor._get_pending_queue()

        # Verify MCP tool was called
        processor.ill_tools["get_pending_inbound_queue"].assert_called_once()

        # Verify response
        assert len(queue) == 1
        assert queue[0]["id"] == "loan-001"

    @pytest.mark.asyncio
    async def test_checks_availability_via_mcp(self, inbound_processor_with_mock_tools):
        """Processor should call check_availability for each instance."""
        processor = inbound_processor_with_mock_tools

        availability = await processor._check_availability("hanno-book-001-inst-001")

        # Verify MCP tool was called
        processor.catalog_tools["check_availability"].assert_called_once_with(
            "hanno-book-001-inst-001"
        )

        # Verify response
        assert availability["is_available"] is True
        assert availability["available_copies"] == 2

    @pytest.mark.asyncio
    async def test_reserves_instance_via_mcp(self, inbound_processor_with_mock_tools):
        """Processor should reserve instance for approved loans."""
        processor = inbound_processor_with_mock_tools

        # Mock returns JSON string; make it return a dict for simpler testing
        processor.catalog_tools["reserve_instance"].return_value = {"success": True}

        result = await processor._reserve_instance("inst-001", "loan-001")

        # Verify MCP tool was called
        processor.catalog_tools["reserve_instance"].assert_called_once_with(
            instance_id="inst-001",
            reserved_for="ILL:loan-001",
        )

        # Result is returned directly from the tool
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_full_inbound_processing_approve(self, inbound_processor_with_mock_tools):
        """Complete inbound processing: fetch → check → reserve → approve."""
        processor = inbound_processor_with_mock_tools

        # Queue with approvable loan
        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "loan-approve-001",
                "instance_id": "inst-001",
                "requesting_library": "reliable-lib",
                "library_context": {"on_time_return_rate": 0.95},
            }]
        })

        # Instance is available
        processor.catalog_tools["check_availability"].return_value = json.dumps({
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        })

        results = await processor.process_pending_queue()

        # Verify results
        assert results["total_processed"] == 1
        assert len(results["approved"]) == 1
        assert len(results["denied"]) == 0

        # Verify reserve and approve were called
        processor.catalog_tools["reserve_instance"].assert_called_once()
        processor.ill_tools["approve_inbound_loan"].assert_called_once()

    @pytest.mark.asyncio
    async def test_full_inbound_processing_deny_unavailable(self, inbound_processor_with_mock_tools):
        """Deny loan when instance is unavailable."""
        processor = inbound_processor_with_mock_tools

        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "loan-deny-001",
                "instance_id": "inst-unavail",
                "library_context": {"on_time_return_rate": 0.90},
            }]
        })

        # Instance is NOT available
        processor.catalog_tools["check_availability"].return_value = json.dumps({
            "is_available": False,
            "total_copies": 1,
            "available_copies": 0,
            "status": "checked_out",
        })

        results = await processor.process_pending_queue()

        assert results["total_processed"] == 1
        assert len(results["denied"]) == 1
        assert "not available" in results["denied"][0]["reason"].lower()

        # Deny was called, reserve was not
        processor.ill_tools["deny_inbound_loan"].assert_called_once()
        processor.catalog_tools["reserve_instance"].assert_not_called()

    @pytest.mark.asyncio
    async def test_full_inbound_processing_deny_last_copy(self, inbound_processor_with_mock_tools):
        """Deny loan for last/only copy."""
        processor = inbound_processor_with_mock_tools

        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "loan-last-copy",
                "instance_id": "inst-rare",
                "library_context": {"on_time_return_rate": 0.95},
            }]
        })

        # Only copy
        processor.catalog_tools["check_availability"].return_value = json.dumps({
            "is_available": True,
            "total_copies": 1,  # Last copy!
            "available_copies": 1,
        })

        results = await processor.process_pending_queue()

        assert len(results["denied"]) == 1
        assert "last" in results["denied"][0]["reason"].lower() or "only" in results["denied"][0]["reason"].lower()

    @pytest.mark.asyncio
    async def test_full_inbound_processing_deny_poor_return_rate(self, inbound_processor_with_mock_tools):
        """Deny loan from library with poor return rate."""
        processor = inbound_processor_with_mock_tools

        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "loan-bad-lib",
                "instance_id": "inst-001",
                "library_context": {"on_time_return_rate": 0.60},  # Below 75%
            }]
        })

        processor.catalog_tools["check_availability"].return_value = json.dumps({
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        })

        results = await processor.process_pending_queue()

        assert len(results["denied"]) == 1
        assert "return rate" in results["denied"][0]["reason"].lower()

    @pytest.mark.asyncio
    async def test_full_inbound_processing_skip_moderate_rate(self, inbound_processor_with_mock_tools):
        """Skip for manual review with moderate return rate."""
        processor = inbound_processor_with_mock_tools

        processor.ill_tools["get_pending_inbound_queue"].return_value = json.dumps({
            "items": [{
                "id": "loan-moderate",
                "instance_id": "inst-001",
                "library_context": {"on_time_return_rate": 0.80},  # Between 75-90%
            }]
        })

        processor.catalog_tools["check_availability"].return_value = json.dumps({
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        })

        results = await processor.process_pending_queue()

        assert len(results["skipped"]) == 1
        assert "manual review" in results["skipped"][0]["reason"].lower()


# =============================================================================
# Policy Evaluation Unit Tests (no MCP needed)
# =============================================================================


class TestILLApprovalPolicyEvaluation:
    """Unit tests for ILL approval policy rules."""

    def test_approve_good_patron_good_library(self):
        """Approve: patron with low fines, reliable library."""
        request = {
            "id": "req-001",
            "library_context": {"fulfillment_rate": 0.90},
        }
        eligibility = {
            "eligible": True,
            "total_fines": 2.00,
            "issues": [],
        }

        decision, reason = evaluate_request_for_approval(request, eligibility)

        assert decision == "approve"
        assert "good standing" in reason.lower()

    def test_deny_blocked_patron(self):
        """Deny: patron account is blocked."""
        request = {"id": "req-001"}
        eligibility = {
            "eligible": False,
            "total_fines": 0,
            "issues": [{"type": "blocked", "reason": "Account blocked"}],
        }

        decision, reason = evaluate_request_for_approval(request, eligibility)

        assert decision == "deny"
        assert "blocked" in reason.lower()

    def test_deny_excessive_fines(self):
        """Deny: patron has fines >= $10."""
        request = {"id": "req-001"}
        eligibility = {
            "eligible": False,
            "total_fines": 12.50,
            "issues": [{"type": "fines", "amount": 12.50}],
        }

        decision, reason = evaluate_request_for_approval(request, eligibility)

        assert decision == "deny"
        assert "fines" in reason.lower()

    def test_deny_low_fulfillment_rate(self):
        """Deny: source library has <70% fulfillment."""
        request = {
            "id": "req-001",
            "library_context": {"fulfillment_rate": 0.65},
        }
        eligibility = {"eligible": True, "total_fines": 0, "issues": []}

        decision, reason = evaluate_request_for_approval(request, eligibility)

        assert decision == "deny"
        assert "fulfillment" in reason.lower()

    def test_skip_moderate_fines(self):
        """Skip: patron fines between $5-$10."""
        request = {"id": "req-001", "library_context": {}}
        eligibility = {
            "eligible": True,
            "total_fines": 7.00,
            "issues": [],
        }

        decision, reason = evaluate_request_for_approval(request, eligibility)

        assert decision == "skip"
        assert "manual review" in reason.lower()


class TestInboundLoanPolicyEvaluation:
    """Unit tests for inbound loan policy rules."""

    def test_approve_available_good_library(self):
        """Approve: available instance from reliable library."""
        loan = {
            "id": "loan-001",
            "library_context": {"on_time_return_rate": 0.92},
        }
        availability = {
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        }

        decision, reason = evaluate_inbound_loan(loan, availability)

        assert decision == "approve"

    def test_deny_unavailable(self):
        """Deny: instance not available."""
        loan = {"id": "loan-001"}
        availability = {
            "is_available": False,
            "total_copies": 1,
            "available_copies": 0,
        }

        decision, reason = evaluate_inbound_loan(loan, availability)

        assert decision == "deny"
        assert "not available" in reason.lower()

    def test_deny_last_copy(self):
        """Deny: only/last copy."""
        loan = {
            "id": "loan-001",
            "library_context": {"on_time_return_rate": 0.95},
        }
        availability = {
            "is_available": True,
            "total_copies": 1,
            "available_copies": 1,
        }

        decision, reason = evaluate_inbound_loan(loan, availability)

        assert decision == "deny"
        assert "last" in reason.lower() or "only" in reason.lower()

    def test_deny_poor_return_rate(self):
        """Deny: poor on-time return rate (<75%)."""
        loan = {
            "id": "loan-001",
            "library_context": {"on_time_return_rate": 0.70},
        }
        availability = {
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        }

        decision, reason = evaluate_inbound_loan(loan, availability)

        assert decision == "deny"
        assert "return rate" in reason.lower()

    def test_skip_moderate_return_rate(self):
        """Skip: moderate return rate (75-90%)."""
        loan = {
            "id": "loan-001",
            "library_context": {"on_time_return_rate": 0.82},
        }
        availability = {
            "is_available": True,
            "total_copies": 5,
            "available_copies": 3,
        }

        decision, reason = evaluate_inbound_loan(loan, availability)

        assert decision == "skip"
        assert "manual review" in reason.lower()
