"""Database models for the ILL service."""

from datetime import datetime, timezone
from sqlmodel import SQLModel, Field


class ILLRequestModel(SQLModel, table=True):
    """
    Outbound ILL request - we're borrowing from another library.

    Tracks the complete lifecycle of requesting a book from an external library
    for one of our patrons.
    """
    __tablename__ = "ill_requests"

    # Primary key
    id: str = Field(primary_key=True)

    # Book information (from external library)
    book_id: str = Field(index=True)  # External library's book ID
    book_title: str                   # Cached for display
    isbn: str | None = Field(default=None, index=True)
    author: str | None = None

    # Patron information (local)
    patron_id: str = Field(index=True)  # Our patron's ID
    patron_reference: str               # Our patron barcode (HAN-P-001)

    # Library information
    source_library: str = Field(index=True)  # e.g., "mastodon-institute"

    # Status tracking
    status: str = Field(index=True)  # pending_approval, approved, requested, shipped, received, in_use, returned, closed, denied
    priority: str = Field(default="normal")  # urgent, high, normal, low

    # Approval tracking
    priority: str = Field(default="normal")  # urgent, high, normal, low
    patron_justification: str | None = None  # Why patron needs this book
    approved_by: str | None = None  # Librarian ID who approved
    approved_at: datetime | None = None  # When approved
    denied_by: str | None = None  # Librarian ID who denied
    denied_at: datetime | None = None  # When denied

    # Timestamps
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    due_date: datetime | None = None
    returned_to_lender_at: datetime | None = None
    closed_at: datetime | None = None

    # Additional fields
    notes: str | None = None
    denial_reason: str | None = None  # If status=denied
    loan_period_days: int | None = None  # Typically 28 days


class InboundLoanModel(SQLModel, table=True):
    """
    Inbound loan - we're lending to another library.

    Tracks items we loan out to other libraries in the network.
    CRITICAL: patron_reference is opaque - we never look up their patron details.
    """
    __tablename__ = "inbound_loans"

    # Primary key
    id: str = Field(primary_key=True)

    # Our book instance being loaned
    instance_id: str = Field(index=True)  # Our physical copy
    book_id: str = Field(index=True)      # Our book ID

    # Requesting library information
    requesting_library: str = Field(index=True)  # e.g., "mastodon-institute"
    patron_reference: str  # THEIR patron ID (opaque to us, no FK)

    # Status tracking
    status: str = Field(index=True)  # pending_approval, approved, shipped, active, returned, denied

    # Approval tracking
    approved_by: str | None = None  # Librarian ID who approved
    denied_by: str | None = None  # Librarian ID who denied
    decision_notes: str | None = None  # Reasoning for approval/denial

    # Timestamps
    requested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))  # When the loan was requested
    approved_at: datetime | None = None
    shipped_at: datetime | None = None
    due_date: datetime | None = None
    returned_at: datetime | None = None

    # Loan terms
    loan_period_days: int = 28  # Standard 28 days for ILL


class ILLAuditTrail(SQLModel, table=True):
    """
    Audit trail for ILL state transitions.

    Tracks all status changes for compliance and debugging.
    """
    __tablename__ = "ill_audit_trail"

    # Primary key
    id: str = Field(primary_key=True)

    # Reference to request or loan
    request_id: str | None = Field(default=None, index=True)  # For outbound requests
    loan_id: str | None = Field(default=None, index=True)     # For inbound loans
    request_type: str  # "outbound" or "inbound"

    # State transition
    from_status: str
    to_status: str

    # Metadata
    changed_by: str | None = None  # Librarian/agent ID who made the change
    change_reason: str | None = None  # Why the change was made
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Additional context
    extra_data: str | None = None  # JSON string for additional context
