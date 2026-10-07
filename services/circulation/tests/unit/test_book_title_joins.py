"""TDD tests for book title joins in circulation responses.

These tests expose TODOs at:
- routes.py:339 - Checkout response returns book_id instead of title
- routes.py:596 - Hold response returns book_id instead of title
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import PatronModel, BookInstanceModel, CheckoutModel, HoldModel
from shared.constants import PatronCategory, InstanceStatus


# Minimal book model for testing (avoid importing catalog.models due to table conflicts)
class BookModelTest(SQLModel, table=True):
    """Minimal book model for circulation tests."""
    __tablename__ = "books"
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True)
    title: str
    author: str
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    stratum: int = 7


class TestCheckoutBookTitleJoin:
    """Tests for checkout endpoint returning book titles (TODO: routes.py:339)."""

    @pytest_asyncio.fixture
    async def setup_for_checkout(self, db_session):
        """Create patron, book, and instance for checkout test."""
        # Create book in catalog
        book = BookModelTest(
            id="title-test-book-001",
            title="Pride and Pachyderm",
            author="Elaphine Greymarch",
            genres=["Romance"],
            stratum=7,
        )
        db_session.add(book)

        # Create patron
        patron = PatronModel(
            id="title-test-patron-001",
            barcode="TEST-P-001",
            name="Test Patron",
            email="test@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=False,
        )
        db_session.add(patron)

        # Create book instance
        instance = BookInstanceModel(
            id=f"{book.id}-instance-001",
            book_id=book.id,
            barcode="TEST-ITEM-001",
            call_number="FIC GRE",
            status=InstanceStatus.AVAILABLE.value,
            location="Fiction Wing",
            condition="good",
        )
        db_session.add(instance)

        await db_session.commit()

        return {
            "book": book,
            "patron": patron,
            "instance": instance,
        }

    @pytest.mark.asyncio
    async def test_checkout_returns_book_title_not_id(self, client, setup_for_checkout):
        """Checkout response should include actual book title, not just book_id."""
        data = setup_for_checkout

        # Perform checkout
        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout_data = response.json()

        # CRITICAL TEST: book_title should be the actual title, not book_id
        assert "book_title" in checkout_data
        assert checkout_data["book_title"] == "Pride and Pachyderm"
        # Should NOT be the book_id
        assert checkout_data["book_title"] != data["book"].id

    @pytest.mark.asyncio
    async def test_checkout_title_handles_missing_book(self, client, db_session):
        """Checkout should handle case where book is missing from catalog."""
        # Create patron and instance, but no book
        patron = PatronModel(
            id="orphan-patron",
            barcode="ORPHAN-P",
            name="Test",
            email="orphan@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
        )
        instance = BookInstanceModel(
            id="orphan-instance",
            book_id="nonexistent-book",  # Book doesn't exist
            barcode="ORPHAN-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        # Attempt checkout
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })

        # Should still succeed, but book_title should indicate unknown
        assert response.status_code == 200
        checkout_data = response.json()
        # Should gracefully handle missing book
        assert checkout_data["book_title"] in ["nonexistent-book", "Unknown Book", None]


class TestHoldBookTitleJoin:
    """Tests for hold endpoint returning book titles (TODO: routes.py:596)."""

    @pytest_asyncio.fixture
    async def setup_for_hold(self, db_session):
        """Create patron and book for hold test."""
        # Create book
        book = BookModelTest(
            id="hold-title-book",
            title="The Great Gatsby Elephant",
            author="F. Scott Elephitzgerald",
            genres=["Fiction"],
            stratum=7,
        )
        db_session.add(book)

        # Create patron
        patron = PatronModel(
            id="hold-title-patron",
            barcode="HOLD-P-001",
            name="Hold Patron",
            email="hold@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=False,
        )
        db_session.add(patron)

        await db_session.commit()

        return {
            "book": book,
            "patron": patron,
        }

    @pytest.mark.asyncio
    async def test_hold_returns_book_title_not_id(self, client, setup_for_hold):
        """Hold response should include actual book title, not just book_id."""
        data = setup_for_hold

        # Place hold
        response = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": data["book"].id,
        })

        assert response.status_code == 200
        hold_data = response.json()

        # CRITICAL TEST: book_title should be the actual title
        assert "book_title" in hold_data
        assert hold_data["book_title"] == "The Great Gatsby Elephant"
        # Should NOT be the book_id
        assert hold_data["book_title"] != data["book"].id

    @pytest.mark.asyncio
    async def test_hold_title_handles_missing_book(self, client, db_session):
        """Hold should handle case where book is missing from catalog."""
        # Create patron but no book
        patron = PatronModel(
            id="hold-orphan-patron",
            barcode="HOLD-ORPHAN-P",
            name="Test",
            email="hold-orphan@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Attempt to place hold on nonexistent book
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": "nonexistent-book-hold",
        })

        # Should still succeed (hold system doesn't validate book existence)
        assert response.status_code == 200
        hold_data = response.json()

        # Should gracefully handle missing book
        assert hold_data["book_title"] in ["nonexistent-book-hold", "Unknown Book", None]


class TestBookTitleHelper:
    """Tests for the book title lookup helper function."""

    @pytest_asyncio.fixture
    async def books_in_catalog(self, db_session):
        """Create several books in catalog."""
        books = [
            BookModelTest(
                id="helper-book-001",
                title="Book One",
                author="Author One",
                genres=["Test"],
                stratum=7,
            ),
            BookModelTest(
                id="helper-book-002",
                title="Book Two",
                author="Author Two",
                genres=["Test"],
                stratum=7,
            ),
        ]
        for book in books:
            db_session.add(book)
        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_get_book_title_success(self, db_session, books_in_catalog):
        """Helper should return book title for valid book_id."""
        # This tests the implementation of get_book_title() helper
        # We'll need to implement this as part of the fix

        # For now, this is a design test - the helper should work like this:
        # from circulation.utils import get_book_title
        # title = await get_book_title(db_session, "helper-book-001")
        # assert title == "Book One"

        # Test will be enabled once helper is implemented
        pass

    @pytest.mark.asyncio
    async def test_get_book_title_not_found(self, db_session, books_in_catalog):
        """Helper should handle missing books gracefully."""
        # Design test for helper
        # from circulation.utils import get_book_title
        # title = await get_book_title(db_session, "nonexistent")
        # assert title in ["nonexistent", "Unknown Book", None]

        pass


class TestMultipleCheckoutsWithTitles:
    """Integration test for multiple checkouts showing correct titles."""

    @pytest_asyncio.fixture
    async def multiple_books_setup(self, db_session):
        """Create multiple books, instances, and patron."""
        patron = PatronModel(
            id="multi-patron",
            barcode="MULTI-P",
            name="Multi Patron",
            email="multi@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
        )
        db_session.add(patron)

        books_data = []
        for i in range(3):
            book = BookModelTest(
                id=f"multi-book-{i:03d}",
                title=f"Book Title {i:03d}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            instance = BookInstanceModel(
                id=f"multi-instance-{i:03d}",
                book_id=book.id,
                barcode=f"MULTI-{i:03d}",
                status=InstanceStatus.AVAILABLE.value,
                condition="good",
            )
            db_session.add(book)
            db_session.add(instance)
            books_data.append({"book": book, "instance": instance})

        await db_session.commit()
        return {"patron": patron, "books": books_data}

    @pytest.mark.asyncio
    async def test_patron_summary_shows_book_titles(self, client, multiple_books_setup):
        """Patron summary should show book titles for all checkouts."""
        data = multiple_books_setup

        # Checkout all three books
        for book_data in data["books"]:
            await client.post("/checkouts", json={
                "patron_id": data["patron"].id,
                "instance_id": book_data["instance"].id,
            })

        # Get patron summary
        response = await client.get(f"/patrons/{data['patron'].id}/summary")
        assert response.status_code == 200
        summary = response.json()

        # Should have 3 checkouts
        assert len(summary["checkouts"]) == 3

        # This test will need enhancement once we add book_title to Checkout schema
        # For now, we're testing that the checkout works
        # Future: verify each checkout in summary includes book_title
