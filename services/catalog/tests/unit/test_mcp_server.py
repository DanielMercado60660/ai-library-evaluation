"""Tests for Catalog MCP Server tools and resources.

These tests verify that the MCP server correctly:
- Exposes book and instance resources
- Executes tools (search, availability, reserve, release)
- Handles edge cases and errors
"""

import json
from datetime import datetime, UTC

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus, ItemCondition


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def book_with_instances(db_session):
    """Create a book with multiple instances for testing."""
    book = BookModel(
        id="book-mcp-001",
        title="The Art of Trunk Management",
        author="Dr. Tuskford Wise",
        isbn="978-0-MCP-0001",
        genres=["Non-fiction", "Self-help"],
        summary="A comprehensive guide to trunk management techniques.",
        publication_year=2020,
        stratum=4,  # Technical/Reference
        publisher="Pachyderm Press",
        page_count=320,
        illustrations=True,
        shelf_location="Reference Wing, Shelf R-5",
    )
    db_session.add(book)

    # Add 3 instances: 2 available, 1 checked out
    instances = [
        BookInstanceModel(
            id="book-mcp-001-inst-001",
            book_id=book.id,
            barcode="HAN-MCP-001",
            call_number="REF 001",
            status=InstanceStatus.AVAILABLE,
            location="Reference Wing, Shelf R-5",
            condition=ItemCondition.GOOD,
        ),
        BookInstanceModel(
            id="book-mcp-001-inst-002",
            book_id=book.id,
            barcode="HAN-MCP-002",
            call_number="REF 001",
            status=InstanceStatus.AVAILABLE,
            location="Reference Wing, Shelf R-5",
            condition=ItemCondition.EXCELLENT,
        ),
        BookInstanceModel(
            id="book-mcp-001-inst-003",
            book_id=book.id,
            barcode="HAN-MCP-003",
            call_number="REF 001",
            status=InstanceStatus.CHECKED_OUT,
            location=None,
            condition=ItemCondition.GOOD,
        ),
    ]
    for inst in instances:
        db_session.add(inst)

    await db_session.commit()
    await db_session.refresh(book)
    return book


@pytest_asyncio.fixture
async def book_single_copy(db_session):
    """Create a book with only one copy."""
    book = BookModel(
        id="book-single-001",
        title="Rare Ivory Manuscripts",
        author="Prof. Ancient Trunk",
        isbn="978-0-RARE-0001",
        genres=["History", "Rare Books"],
        summary="A collection of rare ivory age manuscripts.",
        publication_year=1850,
        stratum=1,  # Noble Tragedies (rare)
        publisher="Antiquarian Press",
        page_count=500,
        illustrations=False,
        shelf_location="Rare Books Vault",
    )
    db_session.add(book)

    instance = BookInstanceModel(
        id="book-single-001-inst-001",
        book_id=book.id,
        barcode="HAN-RARE-001",
        call_number="RARE 001",
        status=InstanceStatus.AVAILABLE,
        location="Rare Books Vault",
        condition=ItemCondition.FAIR,
        condition_notes="Fragile, handle with care",
    )
    db_session.add(instance)

    await db_session.commit()
    await db_session.refresh(book)
    return book


@pytest_asyncio.fixture
async def book_no_available_copies(db_session):
    """Create a book where all copies are checked out."""
    book = BookModel(
        id="book-unavail-001",
        title="Popular Elephant Tales",
        author="Trendy Tusk",
        isbn="978-0-POP-0001",
        genres=["Fiction", "Bestseller"],
        summary="A popular fiction book that's always checked out.",
        publication_year=2023,
        stratum=3,  # Modern Literary Works
        publisher="Bestseller Books",
        page_count=400,
    )
    db_session.add(book)

    # All copies checked out
    for i in range(3):
        instance = BookInstanceModel(
            id=f"book-unavail-001-inst-{i:03d}",
            book_id=book.id,
            barcode=f"HAN-POP-{i:03d}",
            call_number="FIC TUS",
            status=InstanceStatus.CHECKED_OUT,
            location=None,
            condition=ItemCondition.GOOD,
        )
        db_session.add(instance)

    await db_session.commit()
    await db_session.refresh(book)
    return book


@pytest_asyncio.fixture
async def books_by_stratum(db_session):
    """Create books in different strata for filtering tests."""
    strata_books = []
    for stratum in [1, 3, 5, 7]:
        book = BookModel(
            id=f"book-stratum-{stratum}",
            title=f"Stratum {stratum} Book",
            author=f"Author {stratum}",
            isbn=f"978-0-STR{stratum}-001",
            genres=["Test"],
            stratum=stratum,
        )
        db_session.add(book)

        instance = BookInstanceModel(
            id=f"book-stratum-{stratum}-inst-001",
            book_id=book.id,
            barcode=f"HAN-STR{stratum}-001",
            status=InstanceStatus.AVAILABLE,
            condition=ItemCondition.GOOD,
        )
        db_session.add(instance)
        strata_books.append(book)

    await db_session.commit()
    return strata_books


# =============================================================================
# Tests for Search Books Tool
# =============================================================================

class TestSearchBooks:
    """Tests for the search_books MCP tool."""

    @pytest.mark.asyncio
    async def test_search_by_title(self, db_session, book_with_instances):
        """Searching by title should return matching books."""
        from catalog.mcp_server import search_books

        result = await search_books(query="Trunk Management")

        data = json.loads(result)
        assert data["total"] >= 1
        assert any(b["id"] == book_with_instances.id for b in data["books"])

    @pytest.mark.asyncio
    async def test_search_by_author(self, db_session, book_with_instances):
        """Searching by author should return matching books."""
        from catalog.mcp_server import search_books

        result = await search_books(author="Tuskford")

        data = json.loads(result)
        assert data["total"] >= 1
        assert any(b["author"] == book_with_instances.author for b in data["books"])

    @pytest.mark.asyncio
    async def test_search_by_stratum(self, db_session, books_by_stratum):
        """Searching by stratum should return only books in that stratum."""
        from catalog.mcp_server import search_books

        result = await search_books(stratum=5)

        data = json.loads(result)
        # Only stratum 5 book should be returned
        for book in data["books"]:
            assert book.get("stratum") == 5

    @pytest.mark.asyncio
    async def test_search_available_only(self, db_session, book_with_instances, book_no_available_copies):
        """Searching with available_only should exclude unavailable books."""
        from catalog.mcp_server import search_books

        result = await search_books(available_only=True)

        data = json.loads(result)
        # book_no_available_copies should not be in results
        assert not any(b["id"] == book_no_available_copies.id for b in data["books"])

    @pytest.mark.asyncio
    async def test_search_no_results(self, db_session):
        """Searching for non-existent book should return empty list."""
        from catalog.mcp_server import search_books

        result = await search_books(query="Nonexistent Book Title XYZ123")

        data = json.loads(result)
        assert data["total"] == 0
        assert len(data["books"]) == 0


# =============================================================================
# Tests for Check Availability Tool
# =============================================================================

class TestCheckAvailability:
    """Tests for the check_availability MCP tool."""

    @pytest.mark.asyncio
    async def test_availability_with_copies(self, db_session, book_with_instances):
        """Book with available copies should report correct counts."""
        from catalog.mcp_server import check_availability

        result = await check_availability(book_with_instances.id)

        data = json.loads(result)
        assert data["book_id"] == book_with_instances.id
        assert data["total_copies"] == 3
        assert data["available_copies"] == 2
        assert data["is_available"] is True

    @pytest.mark.asyncio
    async def test_availability_all_checked_out(self, db_session, book_no_available_copies):
        """Book with all copies checked out should report unavailable."""
        from catalog.mcp_server import check_availability

        result = await check_availability(book_no_available_copies.id)

        data = json.loads(result)
        assert data["book_id"] == book_no_available_copies.id
        assert data["total_copies"] == 3
        assert data["available_copies"] == 0
        assert data["is_available"] is False

    @pytest.mark.asyncio
    async def test_availability_single_copy(self, db_session, book_single_copy):
        """Book with single available copy should report correctly."""
        from catalog.mcp_server import check_availability

        result = await check_availability(book_single_copy.id)

        data = json.loads(result)
        assert data["book_id"] == book_single_copy.id
        assert data["total_copies"] == 1
        assert data["available_copies"] == 1
        assert data["is_available"] is True

    @pytest.mark.asyncio
    async def test_availability_nonexistent_book(self, db_session):
        """Checking availability of non-existent book should return error."""
        from catalog.mcp_server import check_availability

        result = await check_availability("nonexistent-book-id")

        data = json.loads(result)
        assert "error" in data


# =============================================================================
# Tests for Reserve Instance Tool
# =============================================================================

class TestReserveInstance:
    """Tests for the reserve_instance MCP tool."""

    @pytest.mark.asyncio
    async def test_reserve_available_instance(self, db_session, book_with_instances):
        """Reserving an available instance should succeed."""
        from catalog.mcp_server import reserve_instance

        instance_id = "book-mcp-001-inst-001"  # First available instance
        result = await reserve_instance(instance_id, reason="ILL loan to Mastodon Institute")

        data = json.loads(result)
        assert data["success"] is True
        assert data["instance_id"] == instance_id
        assert data["new_status"] == InstanceStatus.HOLD_SHELF.value

    @pytest.mark.asyncio
    async def test_reserve_checked_out_instance_fails(self, db_session, book_with_instances):
        """Reserving a checked out instance should fail."""
        from catalog.mcp_server import reserve_instance

        instance_id = "book-mcp-001-inst-003"  # Checked out instance
        result = await reserve_instance(instance_id, reason="Test reservation")

        data = json.loads(result)
        assert "error" in data
        assert "not available" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_reserve_nonexistent_instance_fails(self, db_session):
        """Reserving a non-existent instance should fail."""
        from catalog.mcp_server import reserve_instance

        result = await reserve_instance("nonexistent-instance", reason="Test")

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()


# =============================================================================
# Tests for Release Instance Tool
# =============================================================================

class TestReleaseInstance:
    """Tests for the release_instance MCP tool."""

    @pytest.mark.asyncio
    async def test_release_reserved_instance(self, db_session, book_with_instances):
        """Releasing a reserved instance should make it available."""
        from catalog.mcp_server import reserve_instance, release_instance

        # First reserve the instance
        instance_id = "book-mcp-001-inst-001"
        await reserve_instance(instance_id, reason="Test")

        # Then release it
        result = await release_instance(instance_id, reason="Reservation cancelled")

        data = json.loads(result)
        assert data["success"] is True
        assert data["instance_id"] == instance_id
        assert data["new_status"] == InstanceStatus.AVAILABLE.value

    @pytest.mark.asyncio
    async def test_release_nonexistent_instance_fails(self, db_session):
        """Releasing a non-existent instance should fail."""
        from catalog.mcp_server import release_instance

        result = await release_instance("nonexistent-instance", reason="Test")

        data = json.loads(result)
        assert "error" in data


# =============================================================================
# Tests for Get Books by Stratum Tool
# =============================================================================

class TestGetBooksByStratum:
    """Tests for the get_books_by_stratum MCP tool."""

    @pytest.mark.asyncio
    async def test_get_stratum_books(self, db_session, books_by_stratum):
        """Getting books by stratum should return correct books."""
        from catalog.mcp_server import get_books_by_stratum

        result = await get_books_by_stratum(stratum=5)

        data = json.loads(result)
        assert data["stratum"] == 5
        assert data["stratum_name"] == "Children's Tales"
        assert data["total_books"] >= 1

    @pytest.mark.asyncio
    async def test_get_stratum_invalid(self, db_session):
        """Invalid stratum should return error."""
        from catalog.mcp_server import get_books_by_stratum

        result = await get_books_by_stratum(stratum=14)  # Invalid stratum (valid range is 1-13)

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_stratum_empty(self, db_session):
        """Stratum with no books should return empty list."""
        from catalog.mcp_server import get_books_by_stratum

        result = await get_books_by_stratum(stratum=8)  # Translated Works (empty)

        data = json.loads(result)
        assert data["stratum"] == 8
        assert data["total_books"] == 0


# =============================================================================
# Tests for Book Resources
# =============================================================================

class TestBookResources:
    """Tests for book resource data access."""

    @pytest.mark.asyncio
    async def test_get_book_details(self, db_session, book_with_instances):
        """Getting book details should include all fields."""
        from catalog.mcp_server import get_book

        result = await get_book(book_with_instances.id)

        data = json.loads(result)
        assert data["id"] == book_with_instances.id
        assert data["title"] == book_with_instances.title
        assert data["author"] == book_with_instances.author
        assert data["total_copies"] == 3
        assert data["available_copies"] == 2

    @pytest.mark.asyncio
    async def test_get_book_not_found(self, db_session):
        """Getting non-existent book should return error."""
        from catalog.mcp_server import get_book

        result = await get_book("nonexistent-book")

        data = json.loads(result)
        assert "error" in data


class TestInstanceResources:
    """Tests for instance resource data access."""

    @pytest.mark.asyncio
    async def test_get_instance_details(self, db_session, book_with_instances):
        """Getting instance details should include all fields."""
        from catalog.mcp_server import get_instance

        result = await get_instance("book-mcp-001-inst-001")

        data = json.loads(result)
        assert data["id"] == "book-mcp-001-inst-001"
        assert data["book_id"] == book_with_instances.id
        assert data["status"] == InstanceStatus.AVAILABLE.value
        assert "barcode" in data
        assert "condition" in data

    @pytest.mark.asyncio
    async def test_get_instance_not_found(self, db_session):
        """Getting non-existent instance should return error."""
        from catalog.mcp_server import get_instance

        result = await get_instance("nonexistent-instance")

        data = json.loads(result)
        assert "error" in data


class TestCatalogAvailabilityResource:
    """Tests for overall catalog availability resource."""

    @pytest.mark.asyncio
    async def test_catalog_availability_stats(self, db_session, book_with_instances, book_no_available_copies):
        """Catalog availability should return overall statistics."""
        from catalog.mcp_server import get_catalog_availability

        result = await get_catalog_availability()

        data = json.loads(result)
        assert "total_books" in data
        assert "total_instances" in data
        assert "available" in data
        assert "checked_out" in data
        assert "availability_rate" in data
        assert data["total_instances"] >= 6  # 3 + 3 from fixtures
