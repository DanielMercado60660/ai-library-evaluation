"""SQLModel database models for the catalog service."""

import sys

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON

from shared.constants import InstanceStatus, ItemCondition


class BookModel(SQLModel, table=True):
    """Database model for books in the Hanno Memorial Library catalog."""
    __tablename__ = "books"

    id: str = Field(primary_key=True)
    title: str = Field(index=True)
    author: str = Field(index=True)
    isbn: Optional[str] = Field(default=None, index=True)
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    summary: Optional[str] = None
    publication_year: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Hanno catalog fields
    author_dates: Optional[str] = None         # "1580-1642"
    stratum: Optional[int] = Field(default=None, index=True)  # 1-13 classification
    publisher: Optional[str] = None            # "Ivory Stacks Press"
    page_count: Optional[int] = None
    setting_era: Optional[str] = None          # "Ivory Renaissance"
    series: Optional[str] = Field(default=None, index=True)
    series_position: Optional[int] = None
    shelf_location: Optional[str] = None       # "Tragedy Wing, Shelf A-3"
    related_works: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    notes: Optional[str] = None
    in_library: bool = Field(default=True)     # Available at Hanno Memorial

    # Children's book extensions (Stratum V)
    age_range: Optional[str] = None            # "3-6"
    reading_level: Optional[str] = None        # "picture book", "early reader"
    illustrations: bool = Field(default=False)
    illustrator: Optional[str] = None

    # Relationship is read-only in this service; writes are managed via FK fields.
    instances: list["BookInstanceModel"] = Relationship(
        back_populates="book",
        sa_relationship_kwargs={"viewonly": True},
    )


class BookInstanceModel(SQLModel, table=True):
    """Database model for physical book copies."""
    __tablename__ = "book_instances"

    id: str = Field(primary_key=True)
    book_id: str = Field(foreign_key="books.id", index=True)
    barcode: Optional[str] = Field(default=None, unique=True, index=True)  # "HAN-ITEM-000001"
    call_number: Optional[str] = None          # Derived from shelf_location
    status: InstanceStatus = Field(default=InstanceStatus.AVAILABLE, index=True)
    location: Optional[str] = None             # Current physical location
    condition: ItemCondition = Field(default=ItemCondition.GOOD)
    condition_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Relationship is read-only in this service; writes are managed via FK fields.
    book: Optional[BookModel] = Relationship(
        back_populates="instances",
        sa_relationship_kwargs={"viewonly": True},
    )


class PatronModel(SQLModel, table=True):
    """Database model for library patrons at Hanno Memorial Library."""
    __tablename__ = "patrons"

    id: str = Field(primary_key=True)
    barcode: Optional[str] = Field(default=None, unique=True, index=True)  # "HAN-P-001"
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    phone: Optional[str] = None
    category: str = Field(default="adult", index=True)  # adult, youth, staff, researcher, restricted
    checkout_limit: int = Field(default=10)
    hold_limit: int = Field(default=10)
    blocked: bool = Field(default=False)
    block_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CheckoutModel(SQLModel, table=True):
    """Database model for checkouts."""
    __tablename__ = "checkouts"

    id: str = Field(primary_key=True)
    instance_id: str = Field(foreign_key="book_instances.id", index=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    checked_out_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: datetime
    returned_at: Optional[datetime] = None
    status: str = Field(default="active", index=True)  # active, returned, overdue, lost
    renewals_used: int = Field(default=0)
    max_renewals: int = Field(default=2)


class HoldModel(SQLModel, table=True):
    """Database model for holds."""
    __tablename__ = "holds"

    id: str = Field(primary_key=True)
    book_id: str = Field(foreign_key="books.id", index=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    position: int
    status: str = Field(default="pending", index=True)  # pending, ready, expired, fulfilled, cancelled
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    pickup_location: Optional[str] = None
    suspend_until: Optional[datetime] = None


class FineModel(SQLModel, table=True):
    """Database model for fines."""
    __tablename__ = "fines"

    id: str = Field(primary_key=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    checkout_id: Optional[str] = Field(default=None, foreign_key="checkouts.id")
    reason: str  # overdue, lost, damage, processing
    amount: float  # Decimal stored as float for SQLite compatibility
    description: Optional[str] = None
    paid: bool = Field(default=False)
    paid_at: Optional[datetime] = None
    waived: bool = Field(default=False)
    waived_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Keep a single canonical module object even if tests/import machinery resolve
# this module via its workspace path.
sys.modules.setdefault("services.catalog.src.catalog.models", sys.modules[__name__])
