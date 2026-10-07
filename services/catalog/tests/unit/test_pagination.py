"""Unit tests for search pagination logic."""

import pytest
import pytest_asyncio

from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus


class TestPaginationDefaults:
    """Tests for default pagination behavior."""

    @pytest_asyncio.fixture
    async def many_books(self, db_session):
        """Create 50 books for pagination testing."""
        books = []
        for i in range(50):
            book = BookModel(
                id=f"page-book-{i:03d}",
                title=f"Book {i:03d}",
                author=f"Author {i % 10}",  # 10 different authors
                genres=["Test"],
                stratum=(i % 13) + 1,  # Distribute across strata 1-13
            )
            db_session.add(book)

            # Add an instance so book shows up in search
            instance = BookInstanceModel(
                id=f"page-book-{i:03d}-inst",
                book_id=book.id,
                barcode=f"PAGE-{i:03d}",
                status=InstanceStatus.AVAILABLE,
                location="Shelf",
            )
            db_session.add(instance)
            books.append(book)

        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_default_limit(self, client, many_books):
        """Default limit should be 20."""
        response = await client.get("/books")
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 20
        assert data["limit"] == 20
        assert data["offset"] == 0
        assert data["total"] == 50

    @pytest.mark.asyncio
    async def test_default_offset(self, client, many_books):
        """Default offset should be 0."""
        response = await client.get("/books")
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_total_count_accuracy(self, client, many_books):
        """Total should reflect actual count regardless of pagination."""
        response = await client.get("/books", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 50
        assert len(data["books"]) == 5


class TestCustomPagination:
    """Tests for custom limit and offset."""

    @pytest_asyncio.fixture
    async def many_books(self, db_session):
        """Create 50 books."""
        for i in range(50):
            book = BookModel(
                id=f"custom-book-{i:03d}",
                title=f"Book {i:03d}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)
            instance = BookInstanceModel(
                id=f"custom-book-{i:03d}-inst",
                book_id=book.id,
                barcode=f"CUST-{i:03d}",
                status=InstanceStatus.AVAILABLE,
                location="Shelf",
            )
            db_session.add(instance)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_custom_limit_5(self, client, many_books):
        """Should respect custom limit of 5."""
        response = await client.get("/books", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 5
        assert data["limit"] == 5

    @pytest.mark.asyncio
    async def test_custom_limit_50(self, client, many_books):
        """Should respect custom limit of 50."""
        response = await client.get("/books", params={"limit": 50})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 50
        assert data["limit"] == 50

    @pytest.mark.asyncio
    async def test_custom_offset(self, client, many_books):
        """Should respect custom offset."""
        response = await client.get("/books", params={"offset": 10})
        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 10
        # Should still get 20 results (default limit)
        assert len(data["books"]) == 20

    @pytest.mark.asyncio
    async def test_limit_and_offset_combination(self, client, many_books):
        """Should handle both limit and offset together."""
        response = await client.get("/books", params={"limit": 10, "offset": 20})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 10
        assert data["limit"] == 10
        assert data["offset"] == 20
        assert data["total"] == 50


class TestPaginationBoundaries:
    """Tests for pagination boundary conditions."""

    @pytest_asyncio.fixture
    async def books_for_boundaries(self, db_session):
        """Create exactly 25 books."""
        for i in range(25):
            book = BookModel(
                id=f"bound-book-{i:03d}",
                title=f"Book {i:03d}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)
            instance = BookInstanceModel(
                id=f"bound-book-{i:03d}-inst",
                book_id=book.id,
                barcode=f"BOUND-{i:03d}",
                status=InstanceStatus.AVAILABLE,
                location="Shelf",
            )
            db_session.add(instance)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_limit_minimum_boundary(self, client, books_for_boundaries):
        """Minimum limit should be 1."""
        response = await client.get("/books", params={"limit": 1})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert data["limit"] == 1

    @pytest.mark.asyncio
    async def test_limit_below_minimum(self, client, books_for_boundaries):
        """Limit below 1 should return validation error."""
        response = await client.get("/books", params={"limit": 0})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_limit_maximum_boundary(self, client, books_for_boundaries):
        """Maximum limit should be 100."""
        response = await client.get("/books", params={"limit": 100})
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 100
        # Should return all 25 books since limit > total
        assert len(data["books"]) == 25

    @pytest.mark.asyncio
    async def test_limit_above_maximum(self, client, books_for_boundaries):
        """Limit above 100 should return validation error."""
        response = await client.get("/books", params={"limit": 101})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_offset_at_end(self, client, books_for_boundaries):
        """Offset at the last item should return 1 result."""
        response = await client.get("/books", params={"offset": 24, "limit": 10})
        assert response.status_code == 200
        data = response.json()
        # Only 1 book left after offset 24 (book #25)
        assert len(data["books"]) == 1
        assert data["total"] == 25

    @pytest.mark.asyncio
    async def test_offset_beyond_total(self, client, books_for_boundaries):
        """Offset beyond total results should return empty."""
        response = await client.get("/books", params={"offset": 100})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0
        assert data["total"] == 25
        assert data["offset"] == 100

    @pytest.mark.asyncio
    async def test_negative_offset(self, client, books_for_boundaries):
        """Negative offset should return validation error."""
        response = await client.get("/books", params={"offset": -1})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_limit_exceeds_remaining(self, client, books_for_boundaries):
        """When limit exceeds remaining results, return only what's available."""
        response = await client.get("/books", params={"limit": 20, "offset": 20})
        assert response.status_code == 200
        data = response.json()
        # Only 5 books remain after offset 20
        assert len(data["books"]) == 5
        assert data["total"] == 25


class TestPaginationConsistency:
    """Tests for consistent results across pages."""

    @pytest_asyncio.fixture
    async def ordered_books(self, db_session):
        """Create books with predictable IDs for ordering test."""
        for i in range(30):
            book = BookModel(
                id=f"ordered-{i:03d}",
                title=f"Book {i:03d}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)
            instance = BookInstanceModel(
                id=f"ordered-{i:03d}-inst",
                book_id=book.id,
                barcode=f"ORD-{i:03d}",
                status=InstanceStatus.AVAILABLE,
                location="Shelf",
            )
            db_session.add(instance)
        await db_session.commit()

    @pytest.mark.asyncio
    async def test_pagination_no_duplicates(self, client, ordered_books):
        """Pages should not contain duplicate items."""
        # Get first page
        page1 = await client.get("/books", params={"limit": 10, "offset": 0})
        page1_ids = {book["id"] for book in page1.json()["books"]}

        # Get second page
        page2 = await client.get("/books", params={"limit": 10, "offset": 10})
        page2_ids = {book["id"] for book in page2.json()["books"]}

        # Should have no overlap
        assert len(page1_ids & page2_ids) == 0

    @pytest.mark.asyncio
    async def test_pagination_covers_all_items(self, client, ordered_books):
        """All pages together should include all items exactly once."""
        all_ids = set()

        for offset in range(0, 30, 10):
            response = await client.get("/books", params={"limit": 10, "offset": offset})
            page_ids = {book["id"] for book in response.json()["books"]}
            # No duplicates across pages
            assert len(all_ids & page_ids) == 0
            all_ids.update(page_ids)

        # Should have all 30 books
        assert len(all_ids) == 30

    @pytest.mark.asyncio
    async def test_pagination_with_filters_consistent(self, client, db_session):
        """Pagination with filters should have consistent total count."""
        # Create books with specific author
        for i in range(15):
            book = BookModel(
                id=f"filter-page-{i:03d}",
                title=f"Book {i:03d}",
                author="Specific Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)
            instance = BookInstanceModel(
                id=f"filter-page-{i:03d}-inst",
                book_id=book.id,
                barcode=f"FILT-{i:03d}",
                status=InstanceStatus.AVAILABLE,
                location="Shelf",
            )
            db_session.add(instance)
        await db_session.commit()

        # First page with filter
        page1 = await client.get("/books", params={
            "author": "Specific Author",
            "limit": 5,
            "offset": 0,
        })
        assert page1.status_code == 200
        data1 = page1.json()
        assert len(data1["books"]) == 5
        assert data1["total"] == 15

        # Second page with same filter
        page2 = await client.get("/books", params={
            "author": "Specific Author",
            "limit": 5,
            "offset": 5,
        })
        assert page2.status_code == 200
        data2 = page2.json()
        assert len(data2["books"]) == 5
        assert data2["total"] == 15  # Total should be same across pages


class TestEmptyResults:
    """Tests for pagination with empty or minimal results."""

    @pytest.mark.asyncio
    async def test_pagination_empty_database(self, client, db_session):
        """Pagination on empty database should return sensible values."""
        response = await client.get("/books", params={"limit": 10, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 0
        assert data["total"] == 0
        assert data["limit"] == 10
        assert data["offset"] == 0

    @pytest.mark.asyncio
    async def test_pagination_one_result(self, client, db_session):
        """Pagination with single result should work correctly."""
        book = BookModel(
            id="single-book",
            title="Only Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="single-inst",
            book_id=book.id,
            barcode="SINGLE-001",
            status=InstanceStatus.AVAILABLE,
            location="Shelf",
        )
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        response = await client.get("/books", params={"limit": 20, "offset": 0})
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 1
        assert data["total"] == 1
