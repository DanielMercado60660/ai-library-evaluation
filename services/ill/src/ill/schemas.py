"""Pydantic schemas for the ILL service API."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict
from shared.a2a.schemas import A2AMessageEnvelope


# =============================================================================
# Health Check
# =============================================================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    library: str


# =============================================================================
# Outbound Requests (Borrowing)
# =============================================================================

class ILLRequestCreate(BaseModel):
    """Create new ILL request."""
    book_id: str
    patron_id: str
    source_library: str
    isbn: str | None = None
    priority: str = "normal"  # urgent, high, normal, low
    patron_justification: str | None = None
    notes: str | None = None


class ILLRequestResponse(BaseModel):
    """ILL request details."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    book_id: str
    book_title: str
    isbn: str | None
    author: str | None
    patron_id: str
    patron_reference: str
    source_library: str
    status: str
    priority: str
    patron_justification: str | None
    approved_by: str | None
    approved_at: datetime | None
    denied_by: str | None
    denied_at: datetime | None
    requested_at: datetime
    shipped_at: datetime | None
    received_at: datetime | None
    due_date: datetime | None
    returned_to_lender_at: datetime | None
    closed_at: datetime | None
    notes: str | None
    denial_reason: str | None
    loan_period_days: int | None


# =============================================================================
# Inbound Requests (Lending)
# =============================================================================

class InboundQueryRequest(BaseModel):
    """Query holdings from external library."""
    isbn: str | None = None
    title: str | None = None


class InboundQueryResponse(BaseModel):
    """Holdings query response - aggregate data only, NO patron info."""
    isbn: str
    held: bool
    total_copies: int = 0
    available_copies: int = 0
    loanable: bool = False
    loan_period_days: int | None = None
    earliest_return_date: datetime | None = None


class InboundLoanRequest(BaseModel):
    """Request loan from us."""
    isbn: str
    requesting_library: str
    patron_reference: str  # Their patron ID (opaque to us)


class InboundLoanResponse(BaseModel):
    """Loan request response."""
    approved: bool
    request_id: str | None = None
    estimated_ship_date: datetime | None = None
    loan_period_days: int | None = None
    # Denial fields
    reason: str | None = None
    earliest_available: datetime | None = None


class InboundLoanDetails(BaseModel):
    """Details of an inbound loan (for status checks)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    instance_id: str
    book_id: str
    requesting_library: str
    patron_reference: str
    status: str
    approved_by: str | None
    denied_by: str | None
    decision_notes: str | None
    requested_at: datetime
    approved_at: datetime | None
    shipped_at: datetime | None
    due_date: datetime | None
    returned_at: datetime | None
    loan_period_days: int


class ItemReturnedRequest(BaseModel):
    """Mark inbound loan returned."""
    request_id: str


# =============================================================================
# Approval Queue
# =============================================================================

class ApprovalDecisionRequest(BaseModel):
    """Approve or deny a request/loan."""
    librarian_id: str
    notes: str | None = None


class PatronContext(BaseModel):
    """Patron context for approval decisions."""
    patron_id: str
    patron_reference: str
    patron_name: str | None = None
    active_checkouts: int = 0
    active_ill_requests: int = 0
    total_fines: float = 0.0
    is_blocked: bool = False


class LibraryContext(BaseModel):
    """Partner library context for approval decisions."""
    library_code: str
    library_name: str
    fulfillment_rate: float | None = None
    avg_response_time_hours: float | None = None
    on_time_return_rate: float | None = None
    specializations: list[str] = []


class ApprovalQueueItemOutbound(BaseModel):
    """Enriched outbound request for approval queue."""
    # ILL request data
    id: str
    book_id: str
    book_title: str
    isbn: str | None
    author: str | None
    source_library: str
    status: str
    priority: str
    patron_justification: str | None
    requested_at: datetime
    notes: str | None

    # Enriched context
    patron_context: PatronContext
    library_context: LibraryContext
    days_pending: int


class ApprovalQueueItemInbound(BaseModel):
    """Enriched inbound loan request for approval queue."""
    # Inbound loan data
    id: str
    instance_id: str
    book_id: str
    book_title: str | None = None  # Will be enriched from catalog
    requesting_library: str
    patron_reference: str  # Opaque patron ID from requesting library
    status: str
    requested_at: datetime
    loan_period_days: int

    # Enriched context
    library_context: LibraryContext
    instance_available: bool
    days_pending: int


# =============================================================================
# A2A Callback
# =============================================================================


class A2AInboundMessageRequest(BaseModel):
    """Inbound A2A callback payload."""

    message: A2AMessageEnvelope


class A2AInboundMessageResponse(BaseModel):
    """Inbound A2A callback result."""

    accepted: bool
    request_id: str | None = None
    updated_status: str | None = None
