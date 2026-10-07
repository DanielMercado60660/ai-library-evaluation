"""Constants and enums for the AI Library system."""

from enum import Enum


class InstanceStatus(str, Enum):
    """Status of a physical book instance."""
    AVAILABLE = "available"
    CHECKED_OUT = "checked_out"
    HOLD_SHELF = "hold_shelf"
    IN_TRANSIT = "in_transit"
    DROPBOX = "dropbox"
    PROCESSING = "processing"
    IN_REPAIR = "in_repair"
    MISSING = "missing"
    LOST = "lost"
    WITHDRAWN = "withdrawn"


class ItemCondition(str, Enum):
    """Condition of a physical book instance."""
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class CheckoutStatus(str, Enum):
    """Status of a checkout."""
    ACTIVE = "active"
    RETURNED = "returned"
    OVERDUE = "overdue"
    LOST = "lost"


class HoldStatus(str, Enum):
    """Status of a hold request."""
    PENDING = "pending"
    READY = "ready"
    EXPIRED = "expired"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class PatronCategory(str, Enum):
    """Patron category determining loan rules."""
    ADULT = "adult"           # 14-day loans, 10 items
    YOUTH = "youth"           # 14-day loans, 5 items
    STAFF = "staff"           # 30-day loans, 25 items
    RESEARCHER = "researcher" # 60-day loans, 15 items
    RESTRICTED = "restricted" # 7-day loans, 3 items


class FineReason(str, Enum):
    """Reason for a fine."""
    OVERDUE = "overdue"
    LOST = "lost"
    DAMAGE = "damage"
    PROCESSING = "processing"


class OrderStatus(str, Enum):
    """Status of a book order (post-MVP)."""
    REQUESTED = "requested"
    APPROVED = "approved"
    ORDERED = "ordered"
    SHIPPED = "shipped"
    RECEIVED = "received"
    CATALOGED = "cataloged"


class ILLRequestStatus(str, Enum):
    """Status of an outbound ILL request (we're borrowing)."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REQUESTED = "requested"
    SHIPPED = "shipped"
    RECEIVED = "received"
    IN_USE = "in_use"
    RETURNED = "returned"
    CLOSED = "closed"
    DENIED = "denied"


class InboundLoanStatus(str, Enum):
    """Status of an inbound loan (we're lending)."""
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SHIPPED = "shipped"
    ACTIVE = "active"
    RETURNED = "returned"
    DENIED = "denied"


# Hanno Memorial Library constants
LIBRARY_CODE = "HML"
LIBRARY_NAME = "Hanno Memorial Library"

# Patron category loan rules: (loan_days, checkout_limit, hold_limit)
PATRON_LOAN_RULES = {
    PatronCategory.ADULT: (14, 10, 10),
    PatronCategory.YOUTH: (14, 5, 5),
    PatronCategory.STAFF: (30, 25, 25),
    PatronCategory.RESEARCHER: (60, 15, 15),
    PatronCategory.RESTRICTED: (7, 3, 3),
}

# Default values
DEFAULT_CHECKOUT_LIMIT = 10
DEFAULT_HOLD_LIMIT = 10
DEFAULT_LOAN_DAYS = 14
DEFAULT_HOLD_EXPIRY_DAYS = 7
DEFAULT_MAX_RENEWALS = 2
FINE_RATE_PER_DAY = 0.25  # $0.25 per day
MAX_FINE_BEFORE_BLOCK = 10.00  # $10.00

# Inter-Library Loan (ILL) constants
ILL_LOAN_PERIOD_DAYS = 28  # Standard ILL loan period
