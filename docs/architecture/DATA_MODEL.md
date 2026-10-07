## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Data model and schema reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: infrastructure-services

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Data Model

This document defines the entities, relationships, and schemas used throughout the Pachyderm Library Network.

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CATALOG DOMAIN                                  │
│                                                                             │
│  ┌─────────────────┐         1:many         ┌─────────────────┐            │
│  │      BOOK       │◄───────────────────────│  BOOK_INSTANCE  │            │
│  │  (bibliographic │                        │   (physical     │            │
│  │     record)     │                        │     copy)       │            │
│  └────────┬────────┘                        └────────┬────────┘            │
│           │                                          │                      │
│           │ 1:many (holds)                           │ 1:many               │
│           │                                          │                      │
└───────────┼──────────────────────────────────────────┼──────────────────────┘
            │                                          │
            │                                          │
┌───────────┼──────────────────────────────────────────┼──────────────────────┐
│           │            CIRCULATION DOMAIN            │                      │
│           │                                          │                      │
│           ▼                                          ▼                      │
│  ┌─────────────────┐                        ┌─────────────────┐            │
│  │      HOLD       │                        │    CHECKOUT     │            │
│  │                 │                        │                 │            │
│  └────────┬────────┘                        └────────┬────────┘            │
│           │                                          │                      │
│           │ many:1                                   │ many:1               │
│           │                                          │                      │
│           ▼                                          ▼                      │
│  ┌─────────────────────────────────────────────────────────────┐           │
│  │                          PATRON                              │           │
│  │                                                              │           │
│  └──────────────────────────────┬──────────────────────────────┘           │
│                                 │                                           │
│                                 │ 1:many                                    │
│                                 ▼                                           │
│                        ┌─────────────────┐                                 │
│                        │      FINE       │                                 │
│                        └─────────────────┘                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              ILL DOMAIN                                      │
│                                                                             │
│  ┌─────────────────┐                        ┌─────────────────┐            │
│  │   ILL_REQUEST   │◄───────────────────────│   ILL_EVENT     │            │
│  │                 │         1:many         │   (audit log)   │            │
│  └─────────────────┘                        └─────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Catalog Domain

### Book (Bibliographic Record)

The abstract representation of a work — title, author, publication info.

```python
class Book(BaseModel):
    """A book in the catalog (bibliographic record)."""
    
    # Identity
    id: str                          # Internal ID: "book-001"
    isbn: str | None                 # ISBN: "978-0-HANNO-0001"
    
    # Core metadata
    title: str                       # "Tusk and Sensibility"
    author: str                      # "Elaphine Greymarch"
    
    # Classification
    genres: list[str]                # ["fiction", "romance", "classics"]
    stratum: int                     # 1-13, see OVERVIEW.md
    subjects: list[str]              # Controlled vocabulary tags
    
    # Publication
    publisher: str | None            # "Grey Hall Publishing"
    publication_year: int | None     # 1811
    edition: str | None              # "First Edition"
    language: str                    # "Common" (default)
    
    # Physical description
    page_count: int | None           
    format: BookFormat               # hardcover, paperback, etc.
    
    # Series
    series: str | None               # "The Grey Court Saga"
    series_position: int | None      # 1
    
    # Content
    summary: str | None              # Brief description
    cover_url: str | None            # Cover image URL
    
    # Timestamps
    created_at: datetime
    updated_at: datetime


class BookFormat(str, Enum):
    HARDCOVER = "hardcover"
    PAPERBACK = "paperback"
    LEATHER_BOUND = "leather_bound"
    SCROLL = "scroll"              # For ancient texts
    MANUSCRIPT = "manuscript"       # Unique copies
```

### BookInstance (Physical Copy)

A specific physical copy of a book with its own barcode, location, and condition.

```python
class BookInstance(BaseModel):
    """A physical copy of a book."""
    
    # Identity
    id: str                          # "inst-001-a"
    book_id: str                     # FK to Book
    barcode: str                     # "HAN-ITEM-000001"
    
    # Classification
    call_number: str                 # "FIC GRE 1811" (shelf location code)
    
    # Current state
    status: InstanceStatus           # available, checked_out, etc.
    location: str | None             # "shelf-A3", "hold-shelf", null if out
    
    # Condition
    condition: ItemCondition         # excellent, good, fair, poor
    condition_notes: str | None      # "Minor wear on spine"
    
    # Timestamps
    created_at: datetime
    last_status_change: datetime


class InstanceStatus(str, Enum):
    """Status of a physical book instance."""
    
    AVAILABLE = "available"          # On shelf, ready to check out
    CHECKED_OUT = "checked_out"      # With a patron
    HOLD_SHELF = "hold_shelf"        # Waiting for patron to pick up
    IN_TRANSIT = "in_transit"        # Moving between locations
    DROPBOX = "dropbox"              # Returned, awaiting processing
    PROCESSING = "processing"        # Being sorted/shelved
    IN_REPAIR = "in_repair"          # Damaged, being fixed
    MISSING = "missing"              # Can't be located
    LOST = "lost"                    # Confirmed lost
    WITHDRAWN = "withdrawn"          # Removed from collection


class ItemCondition(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"
```

---

## Circulation Domain

### Patron

A library user with borrowing privileges.

```python
class Patron(BaseModel):
    """A library patron."""
    
    # Identity
    id: str                          # "patron-001"
    barcode: str                     # "HAN-P-001" (library card number)
    
    # Personal info (NEVER shared via A2A)
    name: str                        # "Trunsworth Greyvale"
    email: str                       # "t.greyvale@greyhall.edu"
    phone: str | None
    address: str | None
    
    # Membership
    category: PatronCategory         # adult, youth, staff, restricted
    registration_date: datetime
    expiration_date: datetime
    
    # Limits
    checkout_limit: int              # Max items at once
    hold_limit: int                  # Max active holds
    
    # Status
    blocked: bool                    # Can't borrow
    block_reason: str | None         # "Excessive fines"
    
    # Timestamps
    created_at: datetime
    updated_at: datetime


class PatronCategory(str, Enum):
    ADULT = "adult"                  # Standard: 14-day loans, 10 items
    YOUTH = "youth"                  # Under 18: 14-day loans, 5 items
    STAFF = "staff"                  # Extended: 60-day loans, 25 items
    RESEARCHER = "researcher"        # Extended: 30-day loans, 15 items
    RESTRICTED = "restricted"        # Limited: 7-day loans, 3 items
```

### Checkout

A record of a patron borrowing an item.

```python
class Checkout(BaseModel):
    """A checkout record."""
    
    # Identity
    id: str                          # "checkout-001"
    
    # References
    instance_id: str                 # FK to BookInstance
    patron_id: str                   # FK to Patron
    
    # Timing
    checked_out_at: datetime
    due_date: datetime
    returned_at: datetime | None
    
    # Status
    status: CheckoutStatus           # active, returned, overdue
    renewals_used: int               # How many times renewed
    max_renewals: int                # Limit (usually 2)
    
    # Fines
    fines_accrued: Decimal           # If overdue


class CheckoutStatus(str, Enum):
    ACTIVE = "active"                # Currently out
    RETURNED = "returned"            # Brought back
    OVERDUE = "overdue"              # Past due date
    LOST = "lost"                    # Declared lost
```

### Hold

A request for a book that's currently unavailable.

```python
class Hold(BaseModel):
    """A hold request."""
    
    # Identity
    id: str                          # "hold-001"
    
    # References (hold is on a BOOK, not an instance)
    book_id: str                     # FK to Book
    patron_id: str                   # FK to Patron
    
    # Queue
    position: int                    # Position in line (1 = next)
    
    # Status
    status: HoldStatus               # pending, ready, fulfilled, etc.
    
    # Timing
    created_at: datetime
    notified_at: datetime | None     # When we told patron it's ready
    expires_at: datetime | None      # Deadline to pick up
    fulfilled_at: datetime | None    # When checked out
    
    # Preferences
    pickup_location: str | None      # Branch preference
    suspend_until: datetime | None   # "Don't notify until this date"


class HoldStatus(str, Enum):
    PENDING = "pending"              # Waiting in queue
    READY = "ready"                  # Item on hold shelf
    FULFILLED = "fulfilled"          # Patron picked it up
    EXPIRED = "expired"              # Didn't pick up in time
    CANCELLED = "cancelled"          # Patron cancelled
```

### Fine

A charge against a patron's account.

```python
class Fine(BaseModel):
    """A fine or fee."""
    
    # Identity
    id: str                          # "fine-001"
    
    # References
    patron_id: str                   # FK to Patron
    checkout_id: str | None          # FK to Checkout (if applicable)
    
    # Details
    reason: FineReason               # overdue, lost, damage
    amount: Decimal                  # Dollar amount
    description: str | None          # "5 days overdue"
    
    # Status
    paid: bool
    paid_at: datetime | None
    waived: bool                     # Forgiven by staff
    waived_reason: str | None
    
    # Timing
    created_at: datetime


class FineReason(str, Enum):
    OVERDUE = "overdue"              # Late return
    LOST = "lost"                    # Item not returned
    DAMAGE = "damage"                # Item damaged
    PROCESSING = "processing"        # Administrative fee
```

---

## ILL Domain

### ILLRequest

An inter-library loan request.

```python
class ILLRequest(BaseModel):
    """An inter-library loan request."""
    
    # Identity
    id: str                          # "ill-001"
    
    # Direction
    direction: ILLDirection          # outbound (borrowing) or inbound (lending)
    
    # References
    book_id: str                     # What book
    patron_id: str | None            # Which patron (outbound only)
    patron_reference: str            # Opaque reference for A2A: "HAN-P-042"
    
    # Libraries
    requesting_library: str          # Who wants it
    lending_library: str             # Who has it
    
    # Status
    status: ILLStatus
    
    # Tracking
    outbound_tracking: str | None    # Shipping to borrower
    return_tracking: str | None      # Shipping back to lender
    
    # Timing
    created_at: datetime
    approved_at: datetime | None
    shipped_at: datetime | None
    received_at: datetime | None
    due_date: datetime | None
    returned_at: datetime | None
    completed_at: datetime | None
    
    # Notes
    notes: str | None
    denial_reason: str | None


class ILLDirection(str, Enum):
    OUTBOUND = "outbound"            # We are borrowing
    INBOUND = "inbound"              # We are lending


class ILLStatus(str, Enum):
    REQUESTED = "requested"          # Initial request
    APPROVED = "approved"            # Lender said yes
    DENIED = "denied"                # Lender said no
    SHIPPED = "shipped"              # In transit to borrower
    RECEIVED = "received"            # Borrower got it
    CHECKED_OUT = "checked_out"      # Patron has it
    RETURNED = "returned"            # In transit back to lender
    COMPLETED = "completed"          # Back home safe
    CANCELLED = "cancelled"          # Cancelled before fulfillment
```

### ILLEvent

Audit log for ILL request lifecycle.

```python
class ILLEvent(BaseModel):
    """Immutable event in ILL request lifecycle."""
    
    id: str
    request_id: str                  # FK to ILLRequest
    event_type: ILLEventType
    timestamp: datetime
    actor: str                       # Who/what triggered this
    data: dict                       # Event-specific details


class ILLEventType(str, Enum):
    REQUEST_CREATED = "request_created"
    HOLDINGS_QUERIED = "holdings_queried"
    LOAN_REQUESTED = "loan_requested"
    LOAN_APPROVED = "loan_approved"
    LOAN_DENIED = "loan_denied"
    ITEM_SHIPPED = "item_shipped"
    ITEM_RECEIVED = "item_received"
    CHECKOUT_TO_PATRON = "checkout_to_patron"
    RETURNED_BY_PATRON = "returned_by_patron"
    ITEM_RETURNED_TO_LENDER = "item_returned_to_lender"
    REQUEST_COMPLETED = "request_completed"
    REQUEST_CANCELLED = "request_cancelled"
```

---

## Database Schema (SQLModel)

```python
# shared/models.py

from datetime import datetime
from decimal import Decimal
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON


class BookModel(SQLModel, table=True):
    """Database model for books."""
    __tablename__ = "books"
    
    id: str = Field(primary_key=True)
    isbn: str | None = Field(default=None, index=True)
    
    title: str = Field(index=True)
    author: str = Field(index=True)
    
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    stratum: int | None = None
    subjects: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    
    publisher: str | None = None
    publication_year: int | None = None
    edition: str | None = None
    language: str = "Common"
    
    page_count: int | None = None
    format: str = "hardcover"
    
    series: str | None = None
    series_position: int | None = None
    
    summary: str | None = None
    cover_url: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    instances: list["BookInstanceModel"] = Relationship(back_populates="book")
    holds: list["HoldModel"] = Relationship(back_populates="book")


class BookInstanceModel(SQLModel, table=True):
    """Database model for physical copies."""
    __tablename__ = "book_instances"
    
    id: str = Field(primary_key=True)
    book_id: str = Field(foreign_key="books.id", index=True)
    barcode: str = Field(unique=True, index=True)
    
    call_number: str | None = None
    
    status: str = "available"
    location: str | None = None
    
    condition: str = "good"
    condition_notes: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_status_change: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    book: BookModel | None = Relationship(back_populates="instances")
    checkouts: list["CheckoutModel"] = Relationship(back_populates="instance")


class PatronModel(SQLModel, table=True):
    """Database model for patrons."""
    __tablename__ = "patrons"
    
    id: str = Field(primary_key=True)
    barcode: str = Field(unique=True, index=True)
    
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    phone: str | None = None
    address: str | None = None
    
    category: str = "adult"
    registration_date: datetime = Field(default_factory=datetime.utcnow)
    expiration_date: datetime
    
    checkout_limit: int = 10
    hold_limit: int = 10
    
    blocked: bool = False
    block_reason: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    checkouts: list["CheckoutModel"] = Relationship(back_populates="patron")
    holds: list["HoldModel"] = Relationship(back_populates="patron")
    fines: list["FineModel"] = Relationship(back_populates="patron")


class CheckoutModel(SQLModel, table=True):
    """Database model for checkouts."""
    __tablename__ = "checkouts"
    
    id: str = Field(primary_key=True)
    
    instance_id: str = Field(foreign_key="book_instances.id", index=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    
    checked_out_at: datetime = Field(default_factory=datetime.utcnow)
    due_date: datetime
    returned_at: datetime | None = None
    
    status: str = "active"
    renewals_used: int = 0
    max_renewals: int = 2
    
    # Relationships
    instance: BookInstanceModel | None = Relationship(back_populates="checkouts")
    patron: PatronModel | None = Relationship(back_populates="checkouts")


class HoldModel(SQLModel, table=True):
    """Database model for holds."""
    __tablename__ = "holds"
    
    id: str = Field(primary_key=True)
    
    book_id: str = Field(foreign_key="books.id", index=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    
    position: int
    status: str = "pending"
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    notified_at: datetime | None = None
    expires_at: datetime | None = None
    fulfilled_at: datetime | None = None
    
    pickup_location: str | None = None
    suspend_until: datetime | None = None
    
    # Relationships
    book: BookModel | None = Relationship(back_populates="holds")
    patron: PatronModel | None = Relationship(back_populates="holds")


class FineModel(SQLModel, table=True):
    """Database model for fines."""
    __tablename__ = "fines"
    
    id: str = Field(primary_key=True)
    
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    checkout_id: str | None = Field(foreign_key="checkouts.id", default=None)
    
    reason: str
    amount: Decimal = Field(decimal_places=2)
    description: str | None = None
    
    paid: bool = False
    paid_at: datetime | None = None
    waived: bool = False
    waived_reason: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    patron: PatronModel | None = Relationship(back_populates="fines")


class ILLRequestModel(SQLModel, table=True):
    """Database model for ILL requests."""
    __tablename__ = "ill_requests"
    
    id: str = Field(primary_key=True)
    
    direction: str  # "outbound" or "inbound"
    
    book_id: str = Field(index=True)
    patron_id: str | None = Field(foreign_key="patrons.id", default=None)
    patron_reference: str
    
    requesting_library: str
    lending_library: str
    
    status: str = "requested"
    
    outbound_tracking: str | None = None
    return_tracking: str | None = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None
    shipped_at: datetime | None = None
    received_at: datetime | None = None
    due_date: datetime | None = None
    returned_at: datetime | None = None
    completed_at: datetime | None = None
    
    notes: str | None = None
    denial_reason: str | None = None


class ILLEventModel(SQLModel, table=True):
    """Database model for ILL events."""
    __tablename__ = "ill_events"
    
    id: str = Field(primary_key=True)
    request_id: str = Field(foreign_key="ill_requests.id", index=True)
    
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
```

---

## Fictional World Data Constraints

All data must conform to the Hanno Memorial world:

### Book Titles
- Must be elephant-themed or parody titles
- No real-world book titles
- Use the stratum system

### Authors
- Use elephant-pun names (Tuskar, Ivoryn, Greymarch, etc.)
- No real-world author names

### Publishers
- Ivory Stacks Press
- Grey Hall Publishing  
- Trunk & Tusk Books
- The Mammoth Press
- Pachyderm Academic

### ISBNs
- Format: `978-0-HANNO-XXXX` (Hanno)
- Format: `978-0-MAST-XXXX` (Mastodon)
- Format: `978-0-MAMM-XXXX` (Mammoth Valley)

### Patron Names
- Use elephant-world names for consistency
- Examples: Trunsworth Greyvale, Ivana Pachydon, Marcus Tuskwell
