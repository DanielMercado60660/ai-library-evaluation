"""Database models for the registry service."""

from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, JSON


class PartnerLibraryModel(SQLModel, table=True):
    """Partner library in the ILL network."""
    __tablename__ = "partner_libraries"

    # Identity
    code: str = Field(primary_key=True)  # "mastodon-institute"
    name: str = Field(index=True)        # "Mastodon Institute Library"
    display_name: str                    # "The Mastodon Institute"

    # Contact Information
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None

    # Operational Details
    status: str = Field(default="active")  # active, suspended, inactive
    member_since: datetime

    # ILL Policies
    lending_enabled: bool = Field(default=True)
    borrowing_enabled: bool = Field(default=True)
    loan_period_days: int = Field(default=28)
    auto_approve_requests: bool = Field(default=False)
    max_concurrent_loans: int | None = None

    # Service Information
    catalog_url: str | None = None       # For A2A lookups
    ill_protocol: str = Field(default="http")  # http, iso-ill, ncip
    shipping_methods: list[str] = Field(default_factory=lambda: ["mail"], sa_column=Column(JSON))

    # Specializations (helps with partner selection)
    specializations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # e.g., ["paleontology", "ancient-history", "technical-manuscripts"]

    # Notes
    notes: str | None = None

    # Relationships
    metrics: "LibraryMetricsModel" = Relationship(back_populates="library")


class LibraryMetricsModel(SQLModel, table=True):
    """Performance metrics for partner libraries."""
    __tablename__ = "library_metrics"

    library_code: str = Field(foreign_key="partner_libraries.code", primary_key=True)

    # Request metrics
    total_requests_sent: int = Field(default=0)
    total_requests_received: int = Field(default=0)
    requests_approved: int = Field(default=0)
    requests_denied: int = Field(default=0)

    # Performance metrics
    avg_response_time_hours: float | None = None
    fulfillment_rate: float | None = None  # % of requests fulfilled
    on_time_return_rate: float | None = None

    # Reliability
    overdue_items_count: int = Field(default=0)
    lost_items_count: int = Field(default=0)

    # Last activity
    last_request_sent: datetime | None = None
    last_request_received: datetime | None = None
    last_updated: datetime

    # Relationship
    library: PartnerLibraryModel = Relationship(back_populates="metrics")
