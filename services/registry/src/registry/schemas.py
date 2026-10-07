"""API schemas for the registry service."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    library: str


# Partner Library Schemas
class PartnerLibraryCreate(BaseModel):
    """Create a new partner library."""
    code: str
    name: str
    display_name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    catalog_url: str | None = None
    lending_enabled: bool = True
    borrowing_enabled: bool = True
    loan_period_days: int = 28
    auto_approve_requests: bool = False
    specializations: list[str] = []
    notes: str | None = None


class PartnerLibraryUpdate(BaseModel):
    """Update partner library information."""
    name: str | None = None
    display_name: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    address: str | None = None
    catalog_url: str | None = None
    status: str | None = None
    lending_enabled: bool | None = None
    borrowing_enabled: bool | None = None
    auto_approve_requests: bool | None = None
    specializations: list[str] | None = None
    notes: str | None = None


class LibraryMetricsResponse(BaseModel):
    """Library performance metrics."""
    model_config = ConfigDict(from_attributes=True)

    library_code: str
    total_requests_sent: int
    total_requests_received: int
    requests_approved: int
    requests_denied: int
    avg_response_time_hours: float | None
    fulfillment_rate: float | None
    on_time_return_rate: float | None
    overdue_items_count: int
    lost_items_count: int
    last_request_sent: datetime | None
    last_request_received: datetime | None


class PartnerLibraryResponse(BaseModel):
    """Partner library details with metrics."""
    model_config = ConfigDict(from_attributes=True)

    code: str
    name: str
    display_name: str
    contact_name: str | None
    contact_email: str | None
    contact_phone: str | None
    address: str | None
    catalog_url: str | None = None
    status: str
    member_since: datetime
    lending_enabled: bool
    borrowing_enabled: bool
    loan_period_days: int
    auto_approve_requests: bool
    specializations: list[str]
    notes: str | None
    metrics: LibraryMetricsResponse | None = None


class LibrarySelectionRequest(BaseModel):
    """Request to get best library for a book."""
    isbn: str | None = None
    title: str | None = None
    author: str | None = None
    genre: str | None = None


class LibrarySelectionResponse(BaseModel):
    """Recommended library for ILL request."""
    library_code: str
    library_name: str
    confidence: str  # high, medium, low
    reasoning: str
    estimated_response_hours: float | None
    fulfillment_rate: float | None
