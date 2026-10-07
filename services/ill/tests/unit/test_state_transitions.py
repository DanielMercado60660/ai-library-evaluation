"""
Unit tests for state transition rules.

Tests verify that state transition validation works correctly for both
outbound and inbound workflows without requiring database access.
"""

import pytest
from shared.constants import ILLRequestStatus, InboundLoanStatus
from ill.state_transitions import (
    is_valid_outbound_transition,
    is_valid_inbound_transition,
    get_outbound_side_effects,
    get_inbound_side_effects,
    OUTBOUND_TRANSITIONS,
    INBOUND_TRANSITIONS,
)


class TestOutboundTransitionValidation:
    """Test outbound ILL request transition rules."""

    def test_valid_transition_from_pending_approval_to_requested(self):
        """Direct approval should allow PENDING_APPROVAL -> REQUESTED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.PENDING_APPROVAL.value,
            ILLRequestStatus.REQUESTED.value
        ) is True

    def test_valid_transition_from_pending_approval_to_denied(self):
        """Denial should allow PENDING_APPROVAL -> DENIED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.PENDING_APPROVAL.value,
            ILLRequestStatus.DENIED.value
        ) is True

    def test_valid_transition_from_requested_to_shipped(self):
        """Normal progression should allow REQUESTED -> SHIPPED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.REQUESTED.value,
            ILLRequestStatus.SHIPPED.value
        ) is True

    def test_valid_transition_from_shipped_to_received(self):
        """Normal progression should allow SHIPPED -> RECEIVED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.SHIPPED.value,
            ILLRequestStatus.RECEIVED.value
        ) is True

    def test_valid_transition_from_received_to_in_use(self):
        """Checkout should allow RECEIVED -> IN_USE."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.RECEIVED.value,
            ILLRequestStatus.IN_USE.value
        ) is True

    def test_valid_transition_from_in_use_to_returned(self):
        """Return should allow IN_USE -> RETURNED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.IN_USE.value,
            ILLRequestStatus.RETURNED.value
        ) is True

    def test_valid_transition_from_returned_to_closed(self):
        """Closure should allow RETURNED -> CLOSED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.RETURNED.value,
            ILLRequestStatus.CLOSED.value
        ) is True

    def test_invalid_transition_from_closed(self):
        """Terminal state CLOSED should not allow any transitions."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.CLOSED.value,
            ILLRequestStatus.REQUESTED.value
        ) is False

    def test_invalid_transition_from_denied(self):
        """Terminal state DENIED should not allow any transitions."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.DENIED.value,
            ILLRequestStatus.REQUESTED.value
        ) is False

    def test_invalid_backward_transition(self):
        """Should not allow backward transitions like SHIPPED -> REQUESTED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.SHIPPED.value,
            ILLRequestStatus.REQUESTED.value
        ) is False

    def test_invalid_skip_transition(self):
        """Should not allow skipping states like REQUESTED -> RECEIVED."""
        assert is_valid_outbound_transition(
            ILLRequestStatus.REQUESTED.value,
            ILLRequestStatus.RECEIVED.value
        ) is False

    def test_invalid_status_string(self):
        """Invalid status strings should return False."""
        assert is_valid_outbound_transition(
            "invalid_status",
            ILLRequestStatus.REQUESTED.value
        ) is False


class TestInboundTransitionValidation:
    """Test inbound loan transition rules."""

    def test_valid_transition_from_pending_approval_to_approved(self):
        """Approval should allow PENDING_APPROVAL -> APPROVED."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.PENDING_APPROVAL.value,
            InboundLoanStatus.APPROVED.value
        ) is True

    def test_valid_transition_from_pending_approval_to_denied(self):
        """Denial should allow PENDING_APPROVAL -> DENIED."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.PENDING_APPROVAL.value,
            InboundLoanStatus.DENIED.value
        ) is True

    def test_valid_transition_from_approved_to_shipped(self):
        """Shipping should allow APPROVED -> SHIPPED."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.APPROVED.value,
            InboundLoanStatus.SHIPPED.value
        ) is True

    def test_valid_transition_from_shipped_to_active(self):
        """Activation should allow SHIPPED -> ACTIVE."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.SHIPPED.value,
            InboundLoanStatus.ACTIVE.value
        ) is True

    def test_valid_transition_from_active_to_returned(self):
        """Return should allow ACTIVE -> RETURNED."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.ACTIVE.value,
            InboundLoanStatus.RETURNED.value
        ) is True

    def test_invalid_transition_from_returned(self):
        """Terminal state RETURNED should not allow transitions."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.RETURNED.value,
            InboundLoanStatus.ACTIVE.value
        ) is False

    def test_invalid_transition_from_denied(self):
        """Terminal state DENIED should not allow transitions."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.DENIED.value,
            InboundLoanStatus.APPROVED.value
        ) is False

    def test_invalid_skip_transition(self):
        """Should not allow skipping states like APPROVED -> ACTIVE."""
        assert is_valid_inbound_transition(
            InboundLoanStatus.APPROVED.value,
            InboundLoanStatus.ACTIVE.value
        ) is False


class TestSideEffects:
    """Test side effect mapping for transitions."""

    def test_received_to_in_use_triggers_checkout(self):
        """RECEIVED -> IN_USE should trigger auto-checkout."""
        effects = get_outbound_side_effects(
            ILLRequestStatus.RECEIVED.value,
            ILLRequestStatus.IN_USE.value
        )
        assert "create_circulation_checkout" in effects

    def test_inbound_approval_triggers_reservation(self):
        """PENDING_APPROVAL -> APPROVED should trigger instance reservation."""
        effects = get_inbound_side_effects(
            InboundLoanStatus.PENDING_APPROVAL.value,
            InboundLoanStatus.APPROVED.value
        )
        assert "reserve_catalog_instance" in effects

    def test_inbound_return_triggers_release(self):
        """ACTIVE -> RETURNED should trigger instance release."""
        effects = get_inbound_side_effects(
            InboundLoanStatus.ACTIVE.value,
            InboundLoanStatus.RETURNED.value
        )
        assert "release_catalog_instance" in effects

    def test_no_side_effects_for_simple_transition(self):
        """Most transitions should have no side effects."""
        effects = get_outbound_side_effects(
            ILLRequestStatus.REQUESTED.value,
            ILLRequestStatus.SHIPPED.value
        )
        assert effects == []


class TestTransitionMappingCompleteness:
    """Verify transition mappings cover all states."""

    def test_all_outbound_states_have_transitions(self):
        """Every outbound status should be in the transition map."""
        for status in ILLRequestStatus:
            assert status in OUTBOUND_TRANSITIONS, \
                f"Status {status} missing from OUTBOUND_TRANSITIONS"

    def test_all_inbound_states_have_transitions(self):
        """Every inbound status should be in the transition map."""
        for status in InboundLoanStatus:
            assert status in INBOUND_TRANSITIONS, \
                f"Status {status} missing from INBOUND_TRANSITIONS"

    def test_transition_targets_are_valid_statuses(self):
        """All transition targets should be valid status values."""
        for source, targets in OUTBOUND_TRANSITIONS.items():
            for target in targets:
                assert target in ILLRequestStatus, \
                    f"Invalid target {target} for source {source}"

        for source, targets in INBOUND_TRANSITIONS.items():
            for target in targets:
                assert target in InboundLoanStatus, \
                    f"Invalid target {target} for source {source}"
