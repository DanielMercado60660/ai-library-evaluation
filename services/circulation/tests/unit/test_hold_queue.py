"""Unit tests for hold queue management.

Tests hold position calculation, queue ordering, limit enforcement, and cancellation logic.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import PatronModel, HoldModel
from shared.constants import PatronCategory, HoldStatus, DEFAULT_HOLD_EXPIRY_DAYS


# Minimal book model for testing
class BookModelTest(SQLModel, table=True):
    """Minimal book model for circulation tests."""
    __tablename__ = "books"
    __table_args__ = {"extend_existing": True}

    id: str = Field(primary_key=True)
    title: str
    author: str
    genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    stratum: int = 7


class TestHoldPositionCalculation:
    """Tests for calculating and assigning hold positions in queue."""

    @pytest_asyncio.fixture
    async def book_with_holds(self, db_session):
        """Create book with existing holds."""
        book = BookModelTest(
            id="queue-book",
            title="Popular Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)

        # Create 3 patrons with existing holds
        holds = []
        for i in range(3):
            patron = PatronModel(
                id=f"queue-patron-{i}",
                barcode=f"QP-{i}",
                name=f"Patron {i}",
                email=f"patron{i}@test.lib",
                category=PatronCategory.ADULT.value,
                hold_limit=10,
            )
            db_session.add(patron)

            hold = HoldModel(
                id=f"queue-hold-{i}",
                book_id=book.id,
                patron_id=patron.id,
                position=i + 1,  # Positions 1, 2, 3
                status=HoldStatus.PENDING.value,
                created_at=datetime.now(UTC) - timedelta(days=3-i),
            )
            db_session.add(hold)
            holds.append(hold)

        await db_session.commit()
        return {"book": book, "holds": holds}

    @pytest.mark.asyncio
    async def test_first_hold_on_book_gets_position_1(self, client, db_session):
        """First hold on a book should get position 1."""
        book = BookModelTest(
            id="first-hold-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="first-hold-patron",
            barcode="FHP",
            name="Patron",
            email="first@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        # Place first hold
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": book.id,
        })

        assert response.status_code == 200
        hold_data = response.json()

        assert hold_data["position"] == 1

    @pytest.mark.asyncio
    async def test_new_hold_gets_next_position(self, client, db_session, book_with_holds):
        """New hold should get position = max(existing positions) + 1."""
        data = book_with_holds

        # Create new patron
        patron = PatronModel(
            id="new-hold-patron",
            barcode="NHP",
            name="New Patron",
            email="new@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Place hold (should get position 4)
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": data["book"].id,
        })

        assert response.status_code == 200
        hold_data = response.json()

        # Should be position 4 (after existing 1, 2, 3)
        assert hold_data["position"] == 4

    @pytest.mark.asyncio
    async def test_holds_ordered_by_position(self, client, db_session, book_with_holds):
        """Query should return holds in position order."""
        data = book_with_holds

        # Get all holds for this book
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel)
            .where(HoldModel.book_id == data["book"].id)
            .order_by(HoldModel.position)
        )
        holds = result.scalars().all()

        # Should be in position order: 1, 2, 3
        assert [h.position for h in holds] == [1, 2, 3]


class TestHoldCancellation:
    """Tests for hold cancellation and position adjustments."""

    @pytest_asyncio.fixture
    async def book_with_five_holds(self, db_session):
        """Create book with 5 holds in queue."""
        book = BookModelTest(
            id="cancel-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)

        holds = []
        for i in range(5):
            patron = PatronModel(
                id=f"cancel-patron-{i}",
                barcode=f"CP-{i}",
                name=f"Patron {i}",
                email=f"cancel{i}@test.lib",
                category=PatronCategory.ADULT.value,
                hold_limit=10,
            )
            db_session.add(patron)

            hold = HoldModel(
                id=f"cancel-hold-{i}",
                book_id=book.id,
                patron_id=patron.id,
                position=i + 1,  # Positions 1-5
                status=HoldStatus.PENDING.value,
                created_at=datetime.now(UTC),
            )
            db_session.add(hold)
            holds.append(hold)

        await db_session.commit()
        return {"book": book, "holds": holds}

    @pytest.mark.asyncio
    async def test_cancel_middle_hold_adjusts_positions(self, client, db_session, book_with_five_holds):
        """Canceling a middle hold maintains position order (positions don't need to be consecutive)."""
        data = book_with_five_holds

        # Cancel hold at position 3
        response = await client.delete(f"/holds/{data['holds'][2].id}")

        assert response.status_code == 200

        # Check remaining holds
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel)
            .where(
                HoldModel.book_id == data["book"].id,
                HoldModel.status != HoldStatus.CANCELLED.value,
            )
            .order_by(HoldModel.position)
        )
        remaining_holds = result.scalars().all()

        # Should have 4 holds remaining
        # Positions maintain their original numbers (don't need to be consecutive)
        assert len(remaining_holds) == 4
        assert [h.position for h in remaining_holds] == [1, 2, 4, 5]

    @pytest.mark.asyncio
    async def test_cancel_first_hold_maintains_queue_order(self, client, db_session, book_with_five_holds):
        """Canceling first hold maintains queue order."""
        data = book_with_five_holds

        # Cancel hold at position 1
        response = await client.delete(f"/holds/{data['holds'][0].id}")

        assert response.status_code == 200

        # Check remaining holds
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel)
            .where(
                HoldModel.book_id == data["book"].id,
                HoldModel.status != HoldStatus.CANCELLED.value,
            )
            .order_by(HoldModel.position)
        )
        remaining_holds = result.scalars().all()

        # Should have 4 holds with original positions maintained
        assert len(remaining_holds) == 4
        assert [h.position for h in remaining_holds] == [2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_cancel_last_hold_no_position_change(self, client, db_session, book_with_five_holds):
        """Canceling last hold shouldn't affect other positions."""
        data = book_with_five_holds

        # Cancel hold at position 5 (last)
        response = await client.delete(f"/holds/{data['holds'][4].id}")

        assert response.status_code == 200

        # Check remaining holds
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel)
            .where(
                HoldModel.book_id == data["book"].id,
                HoldModel.status != HoldStatus.CANCELLED.value,
            )
            .order_by(HoldModel.position)
        )
        remaining_holds = result.scalars().all()

        # Should still be 1, 2, 3, 4
        assert [h.position for h in remaining_holds] == [1, 2, 3, 4]


class TestHoldLimitEnforcement:
    """Tests for hold limits by patron category."""

    @pytest_asyncio.fixture
    async def books_for_hold_limits(self, db_session):
        """Create 15 books for hold limit testing."""
        books = []
        for i in range(15):
            book = BookModelTest(
                id=f"limit-book-{i:02d}",
                title=f"Book {i}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)
            books.append(book)

        await db_session.commit()
        return books

    @pytest.mark.asyncio
    async def test_adult_hold_limit_10(self, client, db_session, books_for_hold_limits):
        """Adult patrons should have 10-hold limit."""
        books = books_for_hold_limits

        patron = PatronModel(
            id="adult-hold-patron",
            barcode="AHL-P",
            name="Adult Patron",
            email="adult-hold@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Place 10 holds - all should succeed
        for i in range(10):
            response = await client.post("/holds", json={
                "patron_id": patron.id,
                "book_id": books[i].id,
            })
            assert response.status_code == 200

        # 11th hold should fail
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": books[10].id,
        })
        assert response.status_code == 400
        error = response.json()
        assert "HOLD_LIMIT_REACHED" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_youth_hold_limit_5(self, client, db_session, books_for_hold_limits):
        """Youth patrons should have 5-hold limit."""
        books = books_for_hold_limits

        patron = PatronModel(
            id="youth-hold-patron",
            barcode="YHL-P",
            name="Youth Patron",
            email="youth-hold@test.lib",
            category=PatronCategory.YOUTH.value,
            hold_limit=5,
        )
        db_session.add(patron)
        await db_session.commit()

        # Place 5 holds
        for i in range(5):
            response = await client.post("/holds", json={
                "patron_id": patron.id,
                "book_id": books[i].id,
            })
            assert response.status_code == 200

        # 6th hold should fail
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": books[5].id,
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_cancelled_holds_dont_count_toward_limit(self, client, db_session, books_for_hold_limits):
        """Cancelled holds should not count toward patron's hold limit."""
        books = books_for_hold_limits

        patron = PatronModel(
            id="cancel-limit-patron",
            barcode="CL-P",
            name="Cancel Patron",
            email="cancel-limit@test.lib",
            category=PatronCategory.YOUTH.value,
            hold_limit=5,
        )
        db_session.add(patron)
        await db_session.commit()

        # Place 5 holds (at limit)
        hold_ids = []
        for i in range(5):
            response = await client.post("/holds", json={
                "patron_id": patron.id,
                "book_id": books[i].id,
            })
            hold_ids.append(response.json()["hold"]["id"])

        # Cancel 2 holds
        await client.delete(f"/holds/{hold_ids[0]}")
        await client.delete(f"/holds/{hold_ids[1]}")

        # Should be able to place 2 more holds
        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": books[5].id,
        })
        assert response.status_code == 200

        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": books[6].id,
        })
        assert response.status_code == 200


class TestHoldExpiry:
    """Tests for hold expiration after notification."""

    @pytest_asyncio.fixture
    async def ready_hold_setup(self, db_session):
        """Create patron with a READY hold."""
        book = BookModelTest(
            id="expiry-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="expiry-patron",
            barcode="EXP-P",
            name="Patron",
            email="expiry@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        now = datetime.now(UTC)
        hold = HoldModel(
            id="expiry-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.READY.value,
            created_at=now - timedelta(days=3),
            notified_at=now,
            expires_at=now + timedelta(days=DEFAULT_HOLD_EXPIRY_DAYS),
        )
        db_session.add(hold)
        await db_session.commit()

        return {"book": book, "patron": patron, "hold": hold}

    @pytest.mark.asyncio
    async def test_ready_hold_has_expiry_date(self, db_session, ready_hold_setup):
        """READY holds should have expiry date set."""
        data = ready_hold_setup

        hold = data["hold"]
        assert hold.expires_at is not None
        assert hold.notified_at is not None

        # Expiry should be 7 days from notification
        expected_expiry = hold.notified_at + timedelta(days=DEFAULT_HOLD_EXPIRY_DAYS)
        time_diff = abs((hold.expires_at - expected_expiry).total_seconds())
        assert time_diff < 1  # Within 1 second

    @pytest.mark.asyncio
    async def test_expired_hold_marked_as_expired(self, db_session):
        """Holds past expiry date should be marked as EXPIRED."""
        # This would require a background job or cron to mark expired holds
        # For now, test the query that would find expired holds

        book = BookModelTest(
            id="expired-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="expired-patron",
            barcode="EXPIRED-P",
            name="Patron",
            email="expired@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        # Create hold that expired yesterday
        now = datetime.now(UTC)
        hold = HoldModel(
            id="past-expiry-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.READY.value,
            created_at=now - timedelta(days=10),
            notified_at=now - timedelta(days=8),
            expires_at=now - timedelta(days=1),  # Expired yesterday
        )
        db_session.add(hold)
        await db_session.commit()

        # Query for expired holds
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(
                HoldModel.status == HoldStatus.READY.value,
                HoldModel.expires_at < now,
            )
        )
        expired_holds = result.scalars().all()

        # Should find the expired hold
        assert len(expired_holds) == 1
        assert expired_holds[0].id == hold.id


class TestHoldStatusTransitions:
    """Tests for hold status state machine."""

    @pytest_asyncio.fixture
    async def hold_for_transitions(self, db_session):
        """Create book, patron, and hold for status testing."""
        book = BookModelTest(
            id="status-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="status-patron",
            barcode="STATUS-P",
            name="Patron",
            email="status@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        hold = HoldModel(
            id="status-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(hold)
        await db_session.commit()

        return {"book": book, "patron": patron, "hold": hold}

    @pytest.mark.asyncio
    async def test_new_hold_starts_as_pending(self, client, db_session):
        """New holds should start in PENDING status."""
        book = BookModelTest(
            id="new-status-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="new-status-patron",
            barcode="NEW-STATUS-P",
            name="Patron",
            email="new-status@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/holds", json={
            "patron_id": patron.id,
            "book_id": book.id,
        })

        assert response.status_code == 200
        hold_data = response.json()

        assert hold_data["hold"]["status"] == HoldStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_cancelled_hold_changes_status(self, client, db_session, hold_for_transitions):
        """Canceling a hold should change status to CANCELLED."""
        data = hold_for_transitions

        response = await client.delete(f"/holds/{data['hold'].id}")

        assert response.status_code == 200

        # Verify status changed
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(HoldModel.id == data['hold'].id)
        )
        hold = result.scalar_one()

        assert hold.status == HoldStatus.CANCELLED.value
