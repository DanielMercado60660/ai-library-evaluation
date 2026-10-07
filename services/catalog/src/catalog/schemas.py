"""Request and response schemas for the catalog service API."""

from pydantic import BaseModel
from shared.schemas import Book, BookInstance, BookWithAvailability, BookAvailability


class BookSearchParams(BaseModel):
    """Query parameters for book search."""
    q: str | None = None        # Search query
    genre: str | None = None    # Filter by genre
    author: str | None = None   # Filter by author
    stratum: int | None = None  # Filter by stratum (1-13)
    series: str | None = None   # Filter by series name
    available: bool | None = None  # Only show available books
    limit: int = 20
    offset: int = 0


class BookSearchResponse(BaseModel):
    """Response for book search."""
    books: list[BookWithAvailability]
    total: int
    limit: int
    offset: int


class BookDetailResponse(BaseModel):
    """Detailed response for a single book."""
    book: Book
    instances: list[BookInstance]
    total_copies: int
    available_copies: int


class BookAvailabilityResponse(BaseModel):
    """Response for book availability check."""
    availability: BookAvailability


class InstanceStatusUpdate(BaseModel):
    """Request to update a book instance status."""
    status: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str
    library: str | None = None
    library_code: str | None = None


class LibraryInfoResponse(BaseModel):
    """Response for library identity and book count."""
    code: str
    name: str
    book_count: int
