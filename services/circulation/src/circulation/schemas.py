"""Request and response schemas for the circulation service API."""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel

from shared.schemas import Patron, Checkout, Hold, Fine


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    library: str | None = None


# Patron responses
class PatronResponse(BaseModel):
    """Response for patron details."""
    patron: Patron
    current_checkouts: int = 0
    active_holds: int = 0
    fines_owed: Decimal = Decimal("0.00")


class PatronSummaryResponse(BaseModel):
    """Summary of patron's library activity."""
    patron: Patron
    checkouts: list[Checkout]
    holds: list[Hold]
    fines: list[Fine]
    total_fines_owed: Decimal = Decimal("0.00")


# Checkout requests and responses
class CheckoutRequest(BaseModel):
    """Request to checkout an item."""
    instance_id: str
    patron_id: str


class CheckoutResponse(BaseModel):
    """Response for checkout."""
    checkout: Checkout
    book_title: str
    renewals_remaining: int


class ReturnRequest(BaseModel):
    """Request to return an item."""
    instance_id: str
    dropbox: bool = False


class ReturnResponse(BaseModel):
    """Response for return."""
    checkout_id: str
    returned_at: datetime
    dropbox: bool
    fines_incurred: Decimal = Decimal("0.00")
    next_hold_patron: str | None = None


class RenewalResponse(BaseModel):
    """Response for renewal."""
    checkout: Checkout
    new_due_date: datetime
    renewals_remaining: int


# Hold requests and responses
class HoldRequest(BaseModel):
    """Request to place a hold."""
    book_id: str
    patron_id: str


class HoldResponse(BaseModel):
    """Response for hold."""
    hold: Hold
    book_title: str
    position: int
    estimated_wait: str | None = None


# Fine responses
class FineListResponse(BaseModel):
    """Response for list of fines."""
    patron_id: str
    total_owed: Decimal
    fines: list[Fine]


class FinePaymentRequest(BaseModel):
    """Request to pay a fine."""
    amount: Decimal
    method: str = "cash"


class FinePaymentResponse(BaseModel):
    """Response for fine payment."""
    fine: Fine
    amount_paid: Decimal
    remaining_balance: Decimal


# Block requests and responses
class BlockPatronRequest(BaseModel):
    """Request to block a patron."""
    reason: str


class BlockPatronResponse(BaseModel):
    """Response for blocking a patron."""
    patron_id: str
    blocked: bool
    block_reason: str | None = None


class UnblockPatronResponse(BaseModel):
    """Response for unblocking a patron."""
    patron_id: str
    blocked: bool


# Error responses
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: dict
