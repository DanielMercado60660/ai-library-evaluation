"""State machine transition rules for ILL workflows."""

from shared.constants import ILLRequestStatus, InboundLoanStatus

# =============================================================================
# Outbound ILL Request Transitions (Borrowing)
# =============================================================================

OUTBOUND_TRANSITIONS = {
    # From PENDING_APPROVAL
    ILLRequestStatus.PENDING_APPROVAL: [
        ILLRequestStatus.APPROVED,
        ILLRequestStatus.REQUESTED,  # Direct approval skips intermediate APPROVED state
        ILLRequestStatus.DENIED,
    ],

    # From APPROVED (intermediate state, auto-transitions to REQUESTED)
    ILLRequestStatus.APPROVED: [
        ILLRequestStatus.REQUESTED,
    ],

    # From REQUESTED
    ILLRequestStatus.REQUESTED: [
        ILLRequestStatus.SHIPPED,
        ILLRequestStatus.DENIED,  # Can be denied by lending library
    ],

    # From SHIPPED
    ILLRequestStatus.SHIPPED: [
        ILLRequestStatus.RECEIVED,
    ],

    # From RECEIVED
    ILLRequestStatus.RECEIVED: [
        ILLRequestStatus.IN_USE,
        ILLRequestStatus.RETURNED,  # Direct return without checkout
    ],

    # From IN_USE
    ILLRequestStatus.IN_USE: [
        ILLRequestStatus.RETURNED,
    ],

    # From RETURNED
    ILLRequestStatus.RETURNED: [
        ILLRequestStatus.CLOSED,
    ],

    # Terminal states (no transitions)
    ILLRequestStatus.CLOSED: [],
    ILLRequestStatus.DENIED: [],
}


# =============================================================================
# Inbound Loan Transitions (Lending)
# =============================================================================

INBOUND_TRANSITIONS = {
    # From PENDING_APPROVAL
    InboundLoanStatus.PENDING_APPROVAL: [
        InboundLoanStatus.APPROVED,
        InboundLoanStatus.DENIED,
    ],

    # From APPROVED
    InboundLoanStatus.APPROVED: [
        InboundLoanStatus.SHIPPED,
    ],

    # From SHIPPED
    InboundLoanStatus.SHIPPED: [
        InboundLoanStatus.ACTIVE,
    ],

    # From ACTIVE
    InboundLoanStatus.ACTIVE: [
        InboundLoanStatus.RETURNED,
    ],

    # Terminal states (no transitions)
    InboundLoanStatus.RETURNED: [],
    InboundLoanStatus.DENIED: [],
}


# =============================================================================
# Side Effects for State Transitions
# =============================================================================

# Define side effects that should be triggered for specific transitions
# Format: (from_state, to_state) -> list of side effect names

OUTBOUND_SIDE_EFFECTS = {
    # When request is received, trigger auto-checkout
    (ILLRequestStatus.RECEIVED, ILLRequestStatus.IN_USE): [
        "create_circulation_checkout",
    ],

    # When returned to lender, update our records
    (ILLRequestStatus.IN_USE, ILLRequestStatus.RETURNED): [
        "notify_lending_library",
    ],
}

INBOUND_SIDE_EFFECTS = {
    # When approved, reserve the instance
    (InboundLoanStatus.PENDING_APPROVAL, InboundLoanStatus.APPROVED): [
        "reserve_catalog_instance",
    ],

    # When shipped, update instance status
    (InboundLoanStatus.APPROVED, InboundLoanStatus.SHIPPED): [
        "update_instance_status_shipped",
    ],

    # When returned, release the instance
    (InboundLoanStatus.ACTIVE, InboundLoanStatus.RETURNED): [
        "release_catalog_instance",
    ],
}


def is_valid_outbound_transition(from_status: str, to_status: str) -> bool:
    """Check if an outbound ILL request transition is valid."""
    try:
        from_enum = ILLRequestStatus(from_status)
        to_enum = ILLRequestStatus(to_status)

        allowed_transitions = OUTBOUND_TRANSITIONS.get(from_enum, [])
        return to_enum in allowed_transitions
    except ValueError:
        # Invalid status value
        return False


def is_valid_inbound_transition(from_status: str, to_status: str) -> bool:
    """Check if an inbound loan transition is valid."""
    try:
        from_enum = InboundLoanStatus(from_status)
        to_enum = InboundLoanStatus(to_status)

        allowed_transitions = INBOUND_TRANSITIONS.get(from_enum, [])
        return to_enum in allowed_transitions
    except ValueError:
        # Invalid status value
        return False


def get_outbound_side_effects(from_status: str, to_status: str) -> list[str]:
    """Get side effects for an outbound transition."""
    try:
        from_enum = ILLRequestStatus(from_status)
        to_enum = ILLRequestStatus(to_status)

        return OUTBOUND_SIDE_EFFECTS.get((from_enum, to_enum), [])
    except ValueError:
        return []


def get_inbound_side_effects(from_status: str, to_status: str) -> list[str]:
    """Get side effects for an inbound transition."""
    try:
        from_enum = InboundLoanStatus(from_status)
        to_enum = InboundLoanStatus(to_status)

        return INBOUND_SIDE_EFFECTS.get((from_enum, to_enum), [])
    except ValueError:
        return []
