"""SQLModel database models for the circulation service.

Note: These models mirror those in the catalog service. In a production system,
models would be in a shared package to avoid duplication. For this evaluation
platform, we duplicate to keep services independent.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field


class CirculationPatronModel(SQLModel, table=True):
    """Database model for library patrons."""
    __tablename__ = "patrons"
    __table_args__ = {"keep_existing": True}

    id: str = Field(primary_key=True)
    barcode: Optional[str] = Field(default=None, unique=True, index=True)
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)
    phone: Optional[str] = None
    category: str = Field(default="adult", index=True)
    checkout_limit: int = Field(default=10)
    hold_limit: int = Field(default=10)
    blocked: bool = Field(default=False)
    block_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CirculationBookInstanceModel(SQLModel, table=True):
    """Database model for physical book copies."""
    __tablename__ = "book_instances"
    __table_args__ = {"keep_existing": True}

    id: str = Field(primary_key=True)
    book_id: str = Field(index=True)  # No FK - referenced book is in catalog service
    barcode: Optional[str] = Field(default=None, unique=True, index=True)
    call_number: Optional[str] = None
    status: str = Field(default="available", index=True)
    location: Optional[str] = None
    condition: str = Field(default="good")
    condition_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CirculationCheckoutModel(SQLModel, table=True):
    """Database model for checkouts."""
    __tablename__ = "checkouts"
    __table_args__ = {"keep_existing": True}

    id: str = Field(primary_key=True)
    instance_id: str = Field(index=True)  # No FK - microservices pattern
    patron_id: str = Field(index=True)  # FK to patrons in same DB is OK
    checked_out_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    due_date: datetime
    returned_at: Optional[datetime] = None
    status: str = Field(default="active", index=True)
    renewals_used: int = Field(default=0)
    max_renewals: int = Field(default=2)


class CirculationHoldModel(SQLModel, table=True):
    """Database model for holds."""
    __tablename__ = "holds"
    __table_args__ = {"keep_existing": True}

    id: str = Field(primary_key=True)
    book_id: str = Field(index=True)  # No FK - book is in catalog service
    patron_id: str = Field(foreign_key="patrons.id", index=True)  # FK OK - same DB
    position: int
    status: str = Field(default="pending", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    notified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    pickup_location: Optional[str] = None
    suspend_until: Optional[datetime] = None


class CirculationFineModel(SQLModel, table=True):
    """Database model for fines."""
    __tablename__ = "fines"
    __table_args__ = {"keep_existing": True}

    id: str = Field(primary_key=True)
    patron_id: str = Field(foreign_key="patrons.id", index=True)
    checkout_id: Optional[str] = Field(default=None, foreign_key="checkouts.id")
    reason: str  # overdue, lost, damage, processing
    amount: float
    description: Optional[str] = None
    paid: bool = Field(default=False)
    paid_at: Optional[datetime] = None
    waived: bool = Field(default=False)
    waived_reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Backward-compatible aliases used throughout the service/tests.
PatronModel = CirculationPatronModel
BookInstanceModel = CirculationBookInstanceModel
CheckoutModel = CirculationCheckoutModel
HoldModel = CirculationHoldModel
FineModel = CirculationFineModel
