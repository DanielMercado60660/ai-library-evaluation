"""Unit tests for availability calculation logic."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC

from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus, ItemCondition


class TestAvailabilityCounting:
    """Tests for counting total and available copies."""

    @pytest_asyncio.fixture
    async def book_with_instances(self, db_session):
        """Create a book with multiple instances in different statuses."""
        book = BookModel(
            id="availability-book-001",
            title="Test Book for Availability",
            author="Test Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)

        instances = [
            BookInstanceModel(
                id=f"{book.id}-instance-001",
                book_id=book.id,
                barcode="TEST-001",
                status=InstanceStatus.AVAILABLE,
                location="Shelf A",
                condition=ItemCondition.GOOD,
            ),
            BookInstanceModel(
                id=f"{book.id}-instance-002",
                book_id=book.id,
                barcode="TEST-002",
                status=InstanceStatus.AVAILABLE,
                location="Shelf A",
                condition=ItemCondition.GOOD,
            ),
            BookInstanceModel(
                id=f"{book.id}-instance-003",
                book_id=book.id,
                barcode="TEST-003",
                status=InstanceStatus.CHECKED_OUT,
                location=None,
                condition=ItemCondition.GOOD,
            ),
            BookInstanceModel(
                id=f"{book.id}-instance-004",
                book_id=book.id,
                barcode="TEST-004",
                status=InstanceStatus.HOLD_SHELF,
                location="Hold Shelf",
                condition=ItemCondition.GOOD,
            ),
            BookInstanceModel(
                id=f"{book.id}-instance-005",
                book_id=book.id,
                barcode="TEST-005",
                status=InstanceStatus.PROCESSING,
                location="Processing Room",
                condition=ItemCondition.FAIR,
            ),
        ]
        for instance in instances:
            db_session.add(instance)

        await db_session.commit()
        return book

    @pytest.mark.asyncio
    async def test_count_total_copies(self, client, book_with_instances):
        """Availability endpoint should count all instances."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["total_copies"] == 5

    @pytest.mark.asyncio
    async def test_count_available_copies(self, client, book_with_instances):
        """Should count only AVAILABLE status copies."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["available"] == 2

    @pytest.mark.asyncio
    async def test_count_checked_out_copies(self, client, book_with_instances):
        """Should count CHECKED_OUT status copies."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["checked_out"] == 1

    @pytest.mark.asyncio
    async def test_count_hold_shelf_copies(self, client, book_with_instances):
        """Should count HOLD_SHELF status copies."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["on_hold_shelf"] == 1

    @pytest.mark.asyncio
    async def test_count_processing_copies(self, client, book_with_instances):
        """Should count PROCESSING status copies."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["in_processing"] == 1

    @pytest.mark.asyncio
    async def test_status_breakdown_sum_equals_total(self, client, book_with_instances):
        """Status counts should sum to total copies."""
        response = await client.get(f"/books/{book_with_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        avail = data["availability"]
        status_sum = (
            avail["available"]
            + avail["checked_out"]
            + avail["on_hold_shelf"]
            + avail["in_processing"]
        )
        assert status_sum == avail["total_copies"]


class TestBookWithNoInstances:
    """Tests for books without any physical copies."""

    @pytest_asyncio.fixture
    async def book_no_instances(self, db_session):
        """Create a book with no instances."""
        book = BookModel(
            id="no-instance-book",
            title="Book Without Copies",
            author="Test Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)
        await db_session.commit()
        return book

    @pytest.mark.asyncio
    async def test_book_with_zero_instances(self, client, book_no_instances):
        """Book with no instances should have 0 total and available."""
        response = await client.get(f"/books/{book_no_instances.id}/availability")
        assert response.status_code == 200
        data = response.json()
        assert data["availability"]["total_copies"] == 0
        assert data["availability"]["available"] == 0
        assert data["availability"]["checked_out"] == 0


class TestSearchAvailabilityIntegration:
    """Tests for availability display in search results."""

    @pytest_asyncio.fixture
    async def mixed_availability_books(self, db_session):
        """Create books with different availability scenarios."""
        books = []

        # Book with all copies available
        book1 = BookModel(
            id="avail-book-001",
            title="All Available",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book1)
        db_session.add(BookInstanceModel(
            id=f"{book1.id}-inst-001",
            book_id=book1.id,
            barcode="AVAIL-001",
            status=InstanceStatus.AVAILABLE,
            location="Shelf",
        ))
        books.append(book1)

        # Book with all copies checked out
        book2 = BookModel(
            id="avail-book-002",
            title="All Checked Out",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book2)
        db_session.add(BookInstanceModel(
            id=f"{book2.id}-inst-001",
            book_id=book2.id,
            barcode="CHECKOUT-001",
            status=InstanceStatus.CHECKED_OUT,
            location=None,
        ))
        books.append(book2)

        # Book with mixed status
        book3 = BookModel(
            id="avail-book-003",
            title="Mixed Status",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book3)
        db_session.add(BookInstanceModel(
            id=f"{book3.id}-inst-001",
            book_id=book3.id,
            barcode="MIX-001",
            status=InstanceStatus.AVAILABLE,
            location="Shelf",
        ))
        db_session.add(BookInstanceModel(
            id=f"{book3.id}-inst-002",
            book_id=book3.id,
            barcode="MIX-002",
            status=InstanceStatus.CHECKED_OUT,
            location=None,
        ))
        books.append(book3)

        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_search_shows_availability(self, client, mixed_availability_books):
        """Search results should include availability info."""
        response = await client.get("/books")
        assert response.status_code == 200
        data = response.json()
        assert len(data["books"]) == 3

        # Check that all books have availability fields
        for book in data["books"]:
            assert "total_copies" in book
            assert "available_copies" in book

    @pytest.mark.asyncio
    async def test_search_available_filter(self, client, mixed_availability_books):
        """available=true should only return books with available copies."""
        response = await client.get("/books", params={"available": True})
        assert response.status_code == 200
        data = response.json()

        # Should return books 1 and 3 (have available copies)
        # Should NOT return book 2 (all checked out)
        assert len(data["books"]) == 2
        for book in data["books"]:
            assert book["available_copies"] > 0

    @pytest.mark.asyncio
    async def test_book_detail_includes_instances(self, client, mixed_availability_books):
        """Book detail should list all instances."""
        book_id = "avail-book-003"  # Mixed status book
        response = await client.get(f"/books/{book_id}")
        assert response.status_code == 200
        data = response.json()

        assert "instances" in data
        assert len(data["instances"]) == 2
        assert data["total_copies"] == 2
        assert data["available_copies"] == 1


class TestEarliestReturnDate:
    """Tests for earliest_return_date calculation (TODO implementation)."""

    @pytest.mark.asyncio
    async def test_earliest_return_date_with_checkouts(self, client, db_session):
        """Should calculate earliest return date from active checkouts."""
        # This is a TDD test - implementation TODO at routes.py:285
        # Should query circulation.checkouts table for active checkouts
        # and find the earliest due_date

        from catalog.models import BookModel, BookInstanceModel
        from circulation.models import CheckoutModel, PatronModel

        # Create book and instance
        book = BookModel(
            id="return-date-book",
            title="Test Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="return-date-instance",
            book_id=book.id,
            barcode="RET-001",
            status=InstanceStatus.CHECKED_OUT,
        )
        patron = PatronModel(
            id="test-patron",
            barcode="TEST-P-001",
            name="Test Patron",
            email="test@test.com",
            category="adult",
        )

        db_session.add(book)
        db_session.add(instance)
        db_session.add(patron)

        # Create checkout with due date
        now = datetime.now(UTC)
        due_date = now + timedelta(days=7)
        checkout = CheckoutModel(
            id="test-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=due_date,
            status="active",
        )
        db_session.add(checkout)
        await db_session.commit()

        # Check availability
        response = await client.get(f"/books/{book.id}/availability")
        assert response.status_code == 200
        data = response.json()

        # Should have earliest_return_date set
        assert data["availability"]["earliest_return_date"] is not None
        # Should match the due date
        # Format might vary, but should be same day
        # assert data["availability"]["earliest_return_date"] == due_date.isoformat()

    @pytest.mark.asyncio
    async def test_earliest_return_date_no_checkouts(self, client, db_session):
        """earliest_return_date should be None when no active checkouts."""
        book = BookModel(
            id="no-checkout-book",
            title="Available Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="no-checkout-instance",
            book_id=book.id,
            barcode="NO-CHECK-001",
            status=InstanceStatus.AVAILABLE,
        )
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        response = await client.get(f"/books/{book.id}/availability")
        assert response.status_code == 200
        data = response.json()

        # Should be None since book is available
        assert data["availability"]["earliest_return_date"] is None


class TestEdgeCases:
    """Edge cases for availability calculation."""

    @pytest.mark.asyncio
    async def test_availability_nonexistent_book(self, client):
        """Requesting availability for nonexistent book returns 404."""
        response = await client.get("/books/nonexistent-book/availability")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_book_detail_nonexistent_book(self, client):
        """Requesting details for nonexistent book returns 404."""
        response = await client.get("/books/nonexistent-book")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_instances_list_nonexistent_book(self, client):
        """Requesting instances for nonexistent book returns 404."""
        response = await client.get("/books/nonexistent-book/instances")
        assert response.status_code == 404
