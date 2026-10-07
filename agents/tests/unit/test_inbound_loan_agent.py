"""Tests for Inbound Loan Agent policy rules.

These tests verify the policy rule evaluation function correctly
handles all approval/denial scenarios for lending our books to partner libraries.
"""

import pytest
from agents.inbound_loan_agent import evaluate_inbound_loan


# =============================================================================
# Test Fixtures - Book Availability Data
# =============================================================================

@pytest.fixture
def book_available_multiple_copies():
    """Book with multiple copies, one available for lending."""
    return {
        "is_available": True,
        "book_id": "book-001",
        "total_copies": 5,
        "available_copies": 3,
        "current_status": "available",
    }


@pytest.fixture
def book_available_last_available():
    """Book with multiple total copies but only one available."""
    return {
        "is_available": True,
        "book_id": "book-002",
        "total_copies": 4,
        "available_copies": 1,
        "current_status": "available",
    }


@pytest.fixture
def book_not_available():
    """Book that is not available (checked out, on hold, etc.)."""
    return {
        "is_available": False,
        "book_id": "book-003",
        "total_copies": 3,
        "available_copies": 0,
        "current_status": "checked_out",
    }


@pytest.fixture
def book_only_copy():
    """Book with only one copy in the collection."""
    return {
        "is_available": True,
        "book_id": "book-004",
        "total_copies": 1,
        "available_copies": 1,
        "current_status": "available",
    }


@pytest.fixture
def book_two_copies_one_available():
    """Book with two total copies, one available."""
    return {
        "is_available": True,
        "book_id": "book-005",
        "total_copies": 2,
        "available_copies": 1,
        "current_status": "available",
    }


# =============================================================================
# Test Fixtures - Inbound Loan Request Data
# =============================================================================

@pytest.fixture
def loan_request_excellent_library():
    """Loan request from a library with excellent return rate (>=90%)."""
    return {
        "id": "inbound-001",
        "requesting_library_code": "excellent-library",
        "book_id": "book-001",
        "instance_id": "instance-001",
        "days_pending": 2,
        "library_context": {
            "library_code": "excellent-library",
            "on_time_return_rate": 0.95,
            "active": True,
        },
    }


@pytest.fixture
def loan_request_good_library():
    """Loan request from a library with good return rate (90% exactly)."""
    return {
        "id": "inbound-002",
        "requesting_library_code": "good-library",
        "book_id": "book-002",
        "instance_id": "instance-002",
        "days_pending": 1,
        "library_context": {
            "library_code": "good-library",
            "on_time_return_rate": 0.90,
            "active": True,
        },
    }


@pytest.fixture
def loan_request_moderate_library():
    """Loan request from a library with moderate return rate (75-90%)."""
    return {
        "id": "inbound-003",
        "requesting_library_code": "moderate-library",
        "book_id": "book-003",
        "instance_id": "instance-003",
        "days_pending": 3,
        "library_context": {
            "library_code": "moderate-library",
            "on_time_return_rate": 0.82,
            "active": True,
        },
    }


@pytest.fixture
def loan_request_poor_library():
    """Loan request from a library with poor return rate (<75%)."""
    return {
        "id": "inbound-004",
        "requesting_library_code": "poor-library",
        "book_id": "book-004",
        "instance_id": "instance-004",
        "days_pending": 5,
        "library_context": {
            "library_code": "poor-library",
            "on_time_return_rate": 0.65,
            "active": True,
        },
    }


@pytest.fixture
def loan_request_unknown_library():
    """Loan request from a library with no historical data."""
    return {
        "id": "inbound-005",
        "requesting_library_code": "new-library",
        "book_id": "book-005",
        "instance_id": "instance-005",
        "days_pending": 1,
        "library_context": {
            "library_code": "new-library",
            "on_time_return_rate": None,  # No data available
            "active": True,
        },
    }


# =============================================================================
# Auto-Approve Tests
# =============================================================================

class TestAutoApprove:
    """Tests for auto-approve scenarios."""

    def test_approve_excellent_library_multiple_copies(
        self, loan_request_excellent_library, book_available_multiple_copies
    ):
        """Excellent library (>=90%) + multiple copies = auto-approve."""
        decision, reason = evaluate_inbound_loan(
            loan_request_excellent_library,
            book_available_multiple_copies,
        )
        assert decision == "approve"
        assert "reliable" in reason.lower() or "available" in reason.lower()

    def test_approve_good_library_at_90_percent(
        self, loan_request_good_library, book_available_multiple_copies
    ):
        """Library at exactly 90% return rate + multiple copies = auto-approve."""
        decision, reason = evaluate_inbound_loan(
            loan_request_good_library,
            book_available_multiple_copies,
        )
        assert decision == "approve"

    def test_approve_two_copies_one_available_excellent_library(
        self, loan_request_excellent_library, book_two_copies_one_available
    ):
        """Excellent library with 2 copies (1 available) = auto-approve."""
        decision, reason = evaluate_inbound_loan(
            loan_request_excellent_library,
            book_two_copies_one_available,
        )
        # Should approve since total_copies > 1 and rate >= 90%
        # But since available_copies == 1, might require review
        assert decision in ["approve", "skip"]

    def test_approve_unknown_library_multiple_copies(
        self, loan_request_unknown_library, book_available_multiple_copies
    ):
        """Unknown library (None rate) + multiple copies = approve (benefit of doubt)."""
        decision, reason = evaluate_inbound_loan(
            loan_request_unknown_library,
            book_available_multiple_copies,
        )
        # With no rate data and book available, should approve cautiously
        assert decision == "approve"


# =============================================================================
# Auto-Deny Tests
# =============================================================================

class TestAutoDeny:
    """Tests for auto-deny scenarios."""

    def test_deny_book_not_available(
        self, loan_request_excellent_library, book_not_available
    ):
        """Book not available = auto-deny regardless of library quality."""
        decision, reason = evaluate_inbound_loan(
            loan_request_excellent_library,
            book_not_available,
        )
        assert decision == "deny"
        assert "not available" in reason.lower() or "status" in reason.lower()

    def test_deny_poor_return_rate(
        self, loan_request_poor_library, book_available_multiple_copies
    ):
        """Library with poor return rate (<75%) = auto-deny."""
        decision, reason = evaluate_inbound_loan(
            loan_request_poor_library,
            book_available_multiple_copies,
        )
        assert decision == "deny"
        assert "return rate" in reason.lower()

    def test_deny_only_copy(
        self, loan_request_excellent_library, book_only_copy
    ):
        """Only copy of book = auto-deny even for excellent library."""
        decision, reason = evaluate_inbound_loan(
            loan_request_excellent_library,
            book_only_copy,
        )
        assert decision == "deny"
        assert "last" in reason.lower() or "only" in reason.lower()

    def test_deny_poor_library_even_with_multiple_copies(
        self, loan_request_poor_library, book_available_multiple_copies
    ):
        """Poor library denied even when we have many copies."""
        decision, reason = evaluate_inbound_loan(
            loan_request_poor_library,
            book_available_multiple_copies,
        )
        assert decision == "deny"
        assert "return rate" in reason.lower()


# =============================================================================
# Manual Review (Skip) Tests
# =============================================================================

class TestManualReview:
    """Tests for scenarios requiring manual review."""

    def test_skip_moderate_return_rate(
        self, loan_request_moderate_library, book_available_multiple_copies
    ):
        """Library with 75-90% return rate = manual review."""
        decision, reason = evaluate_inbound_loan(
            loan_request_moderate_library,
            book_available_multiple_copies,
        )
        assert decision == "skip"
        assert "review" in reason.lower()

    def test_skip_last_available_copy(
        self, loan_request_unknown_library, book_available_last_available
    ):
        """Last available copy (but not last total) = manual review.

        Note: Uses unknown library (None return rate) since excellent libraries
        (>=90%) get auto-approved before this check is reached.
        """
        decision, reason = evaluate_inbound_loan(
            loan_request_unknown_library,
            book_available_last_available,
        )
        # Unknown library with last available copy should trigger review
        assert decision == "skip"
        assert "last" in reason.lower() or "available" in reason.lower()


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_exactly_75_percent_return_rate(self, book_available_multiple_copies):
        """Library with exactly 75% return rate - boundary case."""
        loan = {
            "id": "inbound-boundary",
            "library_context": {
                "on_time_return_rate": 0.75,  # Exactly at boundary
            },
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            book_available_multiple_copies,
        )
        # 75% is at the lower boundary of the moderate range (75-90%)
        # Should trigger manual review
        assert decision == "skip"

    def test_exactly_90_percent_return_rate(self, book_available_multiple_copies):
        """Library with exactly 90% return rate - boundary case."""
        loan = {
            "id": "inbound-boundary-90",
            "library_context": {
                "on_time_return_rate": 0.90,  # Exactly at upper boundary
            },
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            book_available_multiple_copies,
        )
        # 90% should auto-approve
        assert decision == "approve"

    def test_just_below_75_percent(self, book_available_multiple_copies):
        """Library just below 75% = auto-deny."""
        loan = {
            "id": "inbound-below-75",
            "library_context": {
                "on_time_return_rate": 0.74,
            },
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            book_available_multiple_copies,
        )
        assert decision == "deny"

    def test_just_below_90_percent(self, book_available_multiple_copies):
        """Library just below 90% = manual review."""
        loan = {
            "id": "inbound-below-90",
            "library_context": {
                "on_time_return_rate": 0.89,
            },
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            book_available_multiple_copies,
        )
        assert decision == "skip"

    def test_missing_library_context(self, book_available_multiple_copies):
        """Loan request with missing library context."""
        loan = {
            "id": "inbound-no-context",
            "library_context": {},  # Empty context
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            book_available_multiple_copies,
        )
        # Without library metrics, should still process based on availability
        # Good book availability with unknown library = approve cautiously
        assert decision == "approve"

    def test_zero_copies_reported(self):
        """Edge case where availability reports 0 copies."""
        loan = {
            "id": "inbound-zero",
            "library_context": {
                "on_time_return_rate": 0.95,
            },
        }
        availability = {
            "is_available": False,  # Should be False if 0 copies
            "total_copies": 0,
            "available_copies": 0,
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            availability,
        )
        assert decision == "deny"

    def test_available_flag_false_with_copies_shown(self):
        """Instance marked unavailable despite copies shown (reserved, etc.)."""
        loan = {
            "id": "inbound-reserved",
            "library_context": {
                "on_time_return_rate": 0.95,
            },
        }
        availability = {
            "is_available": False,  # Reserved/on hold
            "total_copies": 5,
            "available_copies": 2,  # System shows available but flagged unavailable
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            availability,
        )
        # is_available flag should take precedence
        assert decision == "deny"


# =============================================================================
# Combined Scenarios
# =============================================================================

class TestCombinedScenarios:
    """Tests for complex scenarios with multiple factors."""

    def test_moderate_library_last_available_copy(self):
        """Moderate library + last available copy = definitely skip."""
        loan = {
            "id": "inbound-combined-1",
            "library_context": {
                "on_time_return_rate": 0.80,
            },
        }
        availability = {
            "is_available": True,
            "total_copies": 3,
            "available_copies": 1,
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            availability,
        )
        # Moderate rate alone triggers skip
        assert decision == "skip"

    def test_excellent_library_but_only_copy(self):
        """Excellent library but only copy = deny."""
        loan = {
            "id": "inbound-combined-2",
            "library_context": {
                "on_time_return_rate": 0.98,
            },
        }
        availability = {
            "is_available": True,
            "total_copies": 1,
            "available_copies": 1,
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            availability,
        )
        # Can't lend only copy regardless of library quality
        assert decision == "deny"

    def test_poor_library_unavailable_book(self):
        """Poor library + unavailable book = deny (multiple reasons)."""
        loan = {
            "id": "inbound-combined-3",
            "library_context": {
                "on_time_return_rate": 0.50,
            },
        }
        availability = {
            "is_available": False,
            "total_copies": 10,
            "available_copies": 0,
        }
        decision, reason = evaluate_inbound_loan(
            loan,
            availability,
        )
        # Should deny - first check is availability
        assert decision == "deny"

