"""Tests for ILL Approval Agent policy rules.

These tests verify the policy rule evaluation function correctly
handles all approval/denial scenarios as defined in the agent's policy.
"""

import pytest
from agents.ill_approval_agent import evaluate_request_for_approval


# =============================================================================
# Test Fixtures - Patron Eligibility Data
# =============================================================================

@pytest.fixture
def patron_good_standing():
    """Patron in good standing - eligible for ILL."""
    return {
        "eligible": True,
        "patron_id": "patron-001",
        "patron_name": "Good Patron",
        "total_fines": 0.00,
        "active_checkouts": 3,
        "checkout_limit": 10,
        "blocked": False,
        "issues": None,
    }


@pytest.fixture
def patron_moderate_fines():
    """Patron with moderate fines ($7.50) - still eligible but flagged."""
    return {
        "eligible": True,
        "patron_id": "patron-002",
        "patron_name": "Moderate Fines",
        "total_fines": 7.50,
        "active_checkouts": 2,
        "checkout_limit": 10,
        "blocked": False,
        "issues": None,
    }


@pytest.fixture
def patron_high_fines():
    """Patron with high fines ($12.00) - should be denied."""
    return {
        "eligible": False,
        "patron_id": "patron-003",
        "patron_name": "High Fines",
        "total_fines": 12.00,
        "active_checkouts": 1,
        "checkout_limit": 10,
        "blocked": False,
        "issues": [{"type": "fines", "message": "Outstanding fines exceed limit: $12.00"}],
    }


@pytest.fixture
def patron_blocked():
    """Blocked patron - should be denied."""
    return {
        "eligible": False,
        "patron_id": "patron-004",
        "patron_name": "Blocked Patron",
        "total_fines": 0.00,
        "active_checkouts": 0,
        "checkout_limit": 10,
        "blocked": True,
        "issues": [{"type": "blocked", "message": "Account blocked: Excessive overdue items"}],
    }


@pytest.fixture
def patron_at_limit():
    """Patron at checkout limit - not eligible."""
    return {
        "eligible": False,
        "patron_id": "patron-005",
        "patron_name": "At Limit",
        "total_fines": 2.00,
        "active_checkouts": 10,
        "checkout_limit": 10,
        "blocked": False,
        "issues": [{"type": "checkout_limit", "message": "At checkout limit: 10/10"}],
    }


# =============================================================================
# Test Fixtures - ILL Request Data
# =============================================================================

@pytest.fixture
def request_normal_good_library():
    """Normal priority request from a reliable library."""
    return {
        "id": "ill-req-001",
        "book_id": "book-001",
        "book_title": "Test Book",
        "patron_id": "patron-001",
        "priority": "normal",
        "patron_justification": "Research purposes",
        "days_pending": 2,
        "library_context": {
            "library_code": "mastodon-institute",
            "fulfillment_rate": 0.92,
            "on_time_return_rate": 0.95,
        },
    }


@pytest.fixture
def request_urgent_pending():
    """Urgent priority request pending > 1 day."""
    return {
        "id": "ill-req-002",
        "book_id": "book-002",
        "book_title": "Urgent Book",
        "patron_id": "patron-001",
        "priority": "urgent",
        "patron_justification": "Thesis deadline",
        "days_pending": 3,
        "library_context": {
            "library_code": "mammoth-valley",
            "fulfillment_rate": 0.88,
            "on_time_return_rate": 0.90,
        },
    }


@pytest.fixture
def request_low_fulfillment_library():
    """Request from library with poor fulfillment rate."""
    return {
        "id": "ill-req-003",
        "book_id": "book-003",
        "book_title": "Risky Book",
        "patron_id": "patron-001",
        "priority": "normal",
        "patron_justification": None,
        "days_pending": 1,
        "library_context": {
            "library_code": "unreliable-library",
            "fulfillment_rate": 0.65,  # Below 70% threshold
            "on_time_return_rate": 0.60,
        },
    }


@pytest.fixture
def request_moderate_library():
    """Request from library with moderate fulfillment rate (70-85%)."""
    return {
        "id": "ill-req-004",
        "book_id": "book-004",
        "book_title": "Moderate Book",
        "patron_id": "patron-001",
        "priority": "normal",
        "patron_justification": "General reading",
        "days_pending": 2,
        "library_context": {
            "library_code": "average-library",
            "fulfillment_rate": 0.78,  # Between 70% and 85%
            "on_time_return_rate": 0.80,
        },
    }


@pytest.fixture
def request_long_pending_no_justification():
    """Request pending > 7 days without justification.

    Uses a moderate library (70-85%) so the "long pending" check is reached
    before auto-approve triggers.
    """
    return {
        "id": "ill-req-005",
        "book_id": "book-005",
        "book_title": "Old Request",
        "patron_id": "patron-001",
        "priority": "low",
        "patron_justification": None,  # No justification
        "days_pending": 10,  # > 7 days
        "library_context": {
            "library_code": "moderate-library",
            "fulfillment_rate": 0.80,  # Moderate range to avoid auto-approve
            "on_time_return_rate": 0.82,
        },
    }


# =============================================================================
# Auto-Approve Tests
# =============================================================================

class TestAutoApprove:
    """Tests for auto-approve scenarios."""

    def test_approve_good_patron_good_library(
        self, request_normal_good_library, patron_good_standing
    ):
        """Good patron + good library (>=85%) = auto-approve."""
        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron_good_standing,
        )
        assert decision == "approve"
        assert "good standing" in reason.lower() or "reliable" in reason.lower()

    def test_approve_urgent_request_pending(
        self, request_urgent_pending, patron_good_standing
    ):
        """Urgent request pending > 1 day with eligible patron = auto-approve."""
        decision, reason = evaluate_request_for_approval(
            request_urgent_pending,
            patron_good_standing,
        )
        # May approve via "good standing" path or "urgent priority" path
        assert decision == "approve"

    def test_approve_high_priority_moderate_fines(
        self, request_urgent_pending, patron_moderate_fines
    ):
        """High priority with moderate fines (< $10) should still approve."""
        decision, reason = evaluate_request_for_approval(
            request_urgent_pending,
            patron_moderate_fines,
        )
        # Moderate fines (< $10) shouldn't block urgent requests
        assert decision == "approve"


# =============================================================================
# Auto-Deny Tests
# =============================================================================

class TestAutoDeny:
    """Tests for auto-deny scenarios."""

    def test_deny_blocked_patron(
        self, request_normal_good_library, patron_blocked
    ):
        """Blocked patron = auto-deny."""
        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron_blocked,
        )
        assert decision == "deny"
        assert "blocked" in reason.lower()

    def test_deny_high_fines(
        self, request_normal_good_library, patron_high_fines
    ):
        """Patron with fines >= $10 = auto-deny."""
        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron_high_fines,
        )
        assert decision == "deny"
        assert "fine" in reason.lower() or "$10" in reason

    def test_deny_low_fulfillment_library(
        self, request_low_fulfillment_library, patron_good_standing
    ):
        """Library with fulfillment rate < 70% = auto-deny."""
        decision, reason = evaluate_request_for_approval(
            request_low_fulfillment_library,
            patron_good_standing,
        )
        assert decision == "deny"
        assert "fulfillment" in reason.lower()


# =============================================================================
# Manual Review (Skip) Tests
# =============================================================================

class TestManualReview:
    """Tests for scenarios requiring manual review."""

    def test_skip_moderate_fines(
        self, request_normal_good_library, patron_moderate_fines
    ):
        """Patron with moderate fines ($5-$10) on normal request = manual review."""
        # Update library to be moderate (not excellent) to trigger review
        request_normal_good_library["library_context"]["fulfillment_rate"] = 0.80

        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron_moderate_fines,
        )
        # With moderate library AND moderate fines, should require review
        assert decision == "skip"
        assert "manual review" in reason.lower() or "review" in reason.lower()

    def test_skip_moderate_library(
        self, request_moderate_library, patron_good_standing
    ):
        """Library with 70-85% fulfillment rate = manual review."""
        decision, reason = evaluate_request_for_approval(
            request_moderate_library,
            patron_good_standing,
        )
        assert decision == "skip"
        assert "review" in reason.lower()

    def test_skip_long_pending_no_justification(
        self, request_long_pending_no_justification, patron_good_standing
    ):
        """Request > 7 days without justification = manual review.

        Note: With a moderate library (70-85%), the "moderate library" check
        triggers first. This test verifies the request still goes to manual
        review (which handles the long-pending case indirectly).
        """
        decision, reason = evaluate_request_for_approval(
            request_long_pending_no_justification,
            patron_good_standing,
        )
        assert decision == "skip"
        # May skip for "moderate library" or "long pending" reason
        assert "review" in reason.lower()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_exactly_10_dollar_fines(self, request_normal_good_library):
        """Patron with exactly $10.00 fines should be denied."""
        patron = {
            "eligible": False,
            "patron_id": "patron-edge",
            "total_fines": 10.00,
            "blocked": False,
            "issues": [{"type": "fines", "message": "Outstanding fines exceed limit: $10.00"}],
        }
        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron,
        )
        assert decision == "deny"

    def test_exactly_5_dollar_fines(self, request_normal_good_library):
        """Patron with exactly $5.00 fines - boundary case."""
        patron = {
            "eligible": True,
            "patron_id": "patron-edge",
            "total_fines": 5.00,
            "blocked": False,
            "issues": None,
        }
        # $5.00 is boundary - should trigger review for normal priority
        request_normal_good_library["library_context"]["fulfillment_rate"] = 0.80
        decision, reason = evaluate_request_for_approval(
            request_normal_good_library,
            patron,
        )
        # At exactly $5, with moderate library, should require review
        assert decision == "skip"

    def test_exactly_70_percent_fulfillment(self, patron_good_standing):
        """Library with exactly 70% fulfillment - boundary case."""
        request = {
            "id": "ill-req-boundary",
            "priority": "normal",
            "days_pending": 2,
            "library_context": {
                "fulfillment_rate": 0.70,  # Exactly at boundary
            },
        }
        decision, reason = evaluate_request_for_approval(
            request,
            patron_good_standing,
        )
        # Exactly 70% should require review (70-85% range)
        assert decision == "skip"

    def test_missing_library_context(self, patron_good_standing):
        """Request with missing library context should handle gracefully."""
        request = {
            "id": "ill-req-no-context",
            "priority": "normal",
            "days_pending": 2,
            "library_context": {},  # Empty context
        }
        decision, reason = evaluate_request_for_approval(
            request,
            patron_good_standing,
        )
        # Without library metrics, should still process based on patron
        # Good patron with unknown library might approve or skip
        assert decision in ["approve", "skip"]

    def test_none_fulfillment_rate(self, patron_good_standing):
        """Library with None fulfillment rate (no data)."""
        request = {
            "id": "ill-req-none-rate",
            "priority": "normal",
            "days_pending": 2,
            "library_context": {
                "fulfillment_rate": None,
            },
        }
        decision, reason = evaluate_request_for_approval(
            request,
            patron_good_standing,
        )
        # Unknown rate with good patron - should approve cautiously
        assert decision in ["approve", "skip"]
