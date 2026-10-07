"""Shared Pydantic schemas for the AI Library system."""

from datetime import datetime, UTC
from decimal import Decimal
from pydantic import BaseModel, Field, ConfigDict

from shared.constants import (
    InstanceStatus,
    ItemCondition,
    CheckoutStatus,
    HoldStatus,
    PatronCategory,
    FineReason,
    DEFAULT_CHECKOUT_LIMIT,
    DEFAULT_HOLD_LIMIT,
)


class Book(BaseModel):
    """A book in the Hanno Memorial Library catalog."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    author: str
    isbn: str | None = None
    genres: list[str] = Field(default_factory=list)
    summary: str | None = None
    publication_year: int | None = None

    # Hanno catalog fields
    author_dates: str | None = None       # "1580-1642"
    stratum: int | None = None            # 1-13 classification
    publisher: str | None = None          # "Ivory Stacks Press"
    page_count: int | None = None
    setting_era: str | None = None        # "Ivory Renaissance"
    series: str | None = None
    series_position: int | None = None
    shelf_location: str | None = None     # "Tragedy Wing, Shelf A-3"
    related_works: list[str] = Field(default_factory=list)
    notes: str | None = None

    # Children's book extensions (Stratum V)
    age_range: str | None = None          # "3-6"
    reading_level: str | None = None      # "picture book", "early reader"
    illustrations: bool = False
    illustrator: str | None = None


class BookInstance(BaseModel):
    """A physical copy of a book."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    book_id: str
    barcode: str | None = None            # "HAN-ITEM-000001"
    call_number: str | None = None        # Derived from shelf_location
    status: InstanceStatus = InstanceStatus.AVAILABLE
    location: str | None = None           # e.g., "Tragedy Wing, Shelf A-3"
    condition: ItemCondition = ItemCondition.GOOD
    condition_notes: str | None = None


class Patron(BaseModel):
    """A library patron at Hanno Memorial Library."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    barcode: str | None = None            # "HAN-P-001"
    name: str
    email: str
    phone: str | None = None
    category: PatronCategory = PatronCategory.ADULT
    checkout_limit: int = DEFAULT_CHECKOUT_LIMIT
    hold_limit: int = DEFAULT_HOLD_LIMIT
    blocked: bool = False
    block_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Checkout(BaseModel):
    """A book checkout record."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    instance_id: str
    patron_id: str
    checked_out_at: datetime
    due_date: datetime
    returned_at: datetime | None = None
    status: CheckoutStatus = CheckoutStatus.ACTIVE


class Hold(BaseModel):
    """A hold request for a book."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    book_id: str
    patron_id: str
    position: int  # Position in the hold queue
    status: HoldStatus = HoldStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    notified_at: datetime | None = None
    expires_at: datetime | None = None
    pickup_location: str | None = None
    suspend_until: datetime | None = None


class Fine(BaseModel):
    """A fine against a patron's account."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    patron_id: str
    checkout_id: str | None = None
    reason: FineReason
    amount: Decimal
    description: str | None = None
    paid: bool = False
    paid_at: datetime | None = None
    waived: bool = False
    waived_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Response schemas for API
class BookWithAvailability(Book):
    """Book with availability information."""
    total_copies: int = 0
    available_copies: int = 0


class BookSearchResult(BaseModel):
    """Search result containing books."""
    books: list[BookWithAvailability]
    total: int
    query: str | None = None


class BookAvailability(BaseModel):
    """Detailed availability for a book."""
    book_id: str
    total_copies: int = 0
    available: int = 0
    checked_out: int = 0
    on_hold_shelf: int = 0
    in_processing: int = 0
    earliest_return_date: datetime | None = None


class PatronSummary(BaseModel):
    """Summary of a patron's library activity."""
    patron: Patron
    current_checkouts: int = 0
    active_holds: int = 0
    overdue_count: int = 0
    fines_owed: Decimal = Decimal("0.00")
