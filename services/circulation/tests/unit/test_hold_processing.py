"""TDD tests for hold queue processing on return.

This test exposes TODO at:
- routes.py:529 - Next hold patron determination on return
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import (
    PatronModel,
    BookInstanceModel,
    CheckoutModel,
    HoldModel,
)
from shared.constants import (
    PatronCategory,
    InstanceStatus,
    CheckoutStatus,
    HoldStatus,
    DEFAULT_HOLD_EXPIRY_DAYS,
)


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


class TestHoldQueueProcessing:
    """Tests for hold queue processing when item is returned (TODO: routes.py:529)."""

    @pytest_asyncio.fixture
    async def setup_return_with_holds(self, db_session):
        """Create scenario: item checked out, multiple patrons have holds."""
        # Create book
        book = BookModelTest(
            id="hold-queue-book",
            title="Popular Book",
            author="Famous Author",
            genres=["Fiction"],
            stratum=7,
        )
        db_session.add(book)

        # Create patron who has the book checked out
        patron_with_book = PatronModel(
            id="patron-with-book",
            barcode="PWB-001",
            name="Has Book Patron",
            email="hasbook@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron_with_book)

        # Create instance (checked out)
        instance = BookInstanceModel(
            id="hold-queue-instance",
            book_id=book.id,
            barcode="HQ-ITEM-001",
            call_number="FIC FAM",
            status=InstanceStatus.CHECKED_OUT.value,
            location=None,
            condition="good",
        )
        db_session.add(instance)

        # Create active checkout
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="hold-queue-checkout",
            instance_id=instance.id,
            patron_id=patron_with_book.id,
            checked_out_at=now - timedelta(days=10),
            due_date=now + timedelta(days=4),
            returned_at=None,
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )
        db_session.add(checkout)

        # Create 3 patrons with holds on this book (in queue order)
        hold_patrons = []
        holds = []
        for i in range(3):
            patron = PatronModel(
                id=f"hold-patron-{i+1}",
                barcode=f"HP-{i+1:03d}",
                name=f"Hold Patron {i+1}",
                email=f"hold{i+1}@test.lib",
                category=PatronCategory.ADULT.value,
                hold_limit=10,
            )
            db_session.add(patron)
            hold_patrons.append(patron)

            hold = HoldModel(
                id=f"hold-{i+1}",
                book_id=book.id,
                patron_id=patron.id,
                position=i + 1,  # Position 1, 2, 3
                status=HoldStatus.PENDING.value,
                created_at=now - timedelta(days=5-i),  # First one created earliest
                notified_at=None,
                expires_at=None,
            )
            db_session.add(hold)
            holds.append(hold)

        await db_session.commit()

        return {
            "book": book,
            "instance": instance,
            "checkout": checkout,
            "patron_with_book": patron_with_book,
            "hold_patrons": hold_patrons,
            "holds": holds,
        }

    @pytest.mark.asyncio
    async def test_return_with_holds_notifies_first_patron(self, client, setup_return_with_holds):
        """When item is returned with holds waiting, first patron should be notified."""
        data = setup_return_with_holds

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # CRITICAL TEST: Should identify next hold patron
        assert "next_hold_patron" in return_data
        assert return_data["next_hold_patron"] is not None
        # Should be the first patron in queue (position 1)
        assert return_data["next_hold_patron"] == data["hold_patrons"][0].id

    @pytest.mark.asyncio
    async def test_return_with_holds_updates_hold_status(self, client, db_session, setup_return_with_holds):
        """First hold should transition from PENDING to READY."""
        data = setup_return_with_holds

        # Return the item
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check the first hold's status
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(HoldModel.id == "hold-1")
        )
        first_hold = result.scalar_one()

        # Should be updated to READY
        assert first_hold.status == HoldStatus.READY.value
        # Should have notification timestamp
        assert first_hold.notified_at is not None
        # Should have expiry date (7 days from notification)
        assert first_hold.expires_at is not None

    @pytest.mark.asyncio
    async def test_return_with_holds_sets_expiry_date(self, client, db_session, setup_return_with_holds):
        """Hold expiry should be set to DEFAULT_HOLD_EXPIRY_DAYS after notification."""
        data = setup_return_with_holds

        # Return the item
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check the first hold's expiry
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(HoldModel.id == "hold-1")
        )
        first_hold = result.scalar_one()

        # Calculate expected expiry (notified_at + 7 days)
        expected_expiry = first_hold.notified_at + timedelta(days=DEFAULT_HOLD_EXPIRY_DAYS)

        # Should be approximately 7 days from now (within 1 minute tolerance)
        time_diff = abs((first_hold.expires_at - expected_expiry).total_seconds())
        assert time_diff < 60  # Within 1 minute

    @pytest.mark.asyncio
    async def test_return_with_holds_only_updates_first_hold(self, client, db_session, setup_return_with_holds):
        """Only the first hold should be updated, others remain PENDING."""
        data = setup_return_with_holds

        # Return the item
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check all holds
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(
                HoldModel.book_id == data["book"].id
            ).order_by(HoldModel.position)
        )
        holds = result.scalars().all()

        # First hold should be READY
        assert holds[0].status == HoldStatus.READY.value
        assert holds[0].notified_at is not None

        # Second and third holds should still be PENDING
        assert holds[1].status == HoldStatus.PENDING.value
        assert holds[1].notified_at is None
        assert holds[2].status == HoldStatus.PENDING.value
        assert holds[2].notified_at is None

    @pytest.mark.asyncio
    async def test_return_without_holds_returns_none(self, client, db_session):
        """When no holds exist, next_hold_patron should be None."""
        # Create scenario without holds
        book = BookModelTest(
            id="no-hold-book",
            title="Unpopular Book",
            author="Unknown Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="solo-patron",
            barcode="SOLO-P",
            name="Solo Patron",
            email="solo@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="no-hold-instance",
            book_id=book.id,
            barcode="NO-HOLD-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="no-hold-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": instance.id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # No holds, so next_hold_patron should be None
        assert return_data["next_hold_patron"] is None

    @pytest.mark.asyncio
    async def test_return_with_holds_sets_instance_to_hold_shelf(self, client, db_session, setup_return_with_holds):
        """When holds exist, instance should go to HOLD_SHELF, not AVAILABLE."""
        data = setup_return_with_holds

        # Return the item (not via dropbox)
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check instance status
        from sqlalchemy import select
        result = await db_session.execute(
            select(BookInstanceModel).where(
                BookInstanceModel.id == data["instance"].id
            )
        )
        instance = result.scalar_one()

        # Should be HOLD_SHELF since someone is waiting
        assert instance.status == InstanceStatus.HOLD_SHELF.value
        assert instance.location == "Hold Shelf"

    @pytest.mark.asyncio
    async def test_return_via_dropbox_with_holds(self, client, setup_return_with_holds):
        """Dropbox returns with holds should still trigger hold processing."""
        data = setup_return_with_holds

        # Return via dropbox
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": True,
        })

        assert response.status_code == 200
        return_data = response.json()

        # Should still notify next patron
        assert return_data["next_hold_patron"] == data["hold_patrons"][0].id

    @pytest.mark.asyncio
    async def test_hold_position_consistency_after_notification(self, client, db_session, setup_return_with_holds):
        """Hold positions should remain consistent after one is moved to READY."""
        data = setup_return_with_holds

        # Return the item
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check all hold positions
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(
                HoldModel.book_id == data["book"].id
            ).order_by(HoldModel.position)
        )
        holds = result.scalars().all()

        # Positions should still be 1, 2, 3 (not renumbered)
        assert holds[0].position == 1
        assert holds[1].position == 2
        assert holds[2].position == 3

        # But statuses should differ
        assert holds[0].status == HoldStatus.READY.value
        assert holds[1].status == HoldStatus.PENDING.value
        assert holds[2].status == HoldStatus.PENDING.value


class TestHoldQueueEdgeCases:
    """Edge cases for hold queue processing."""

    @pytest_asyncio.fixture
    async def multiple_ready_holds_scenario(self, db_session):
        """Create scenario with existing READY hold and new PENDING holds."""
        book = BookModelTest(
            id="multi-ready-book",
            title="Test Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="returning-patron",
            barcode="RET-P",
            name="Returning Patron",
            email="ret@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="multi-ready-instance",
            book_id=book.id,
            barcode="MR-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="multi-ready-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        db_session.add(checkout)

        # Create one READY hold (already notified)
        ready_patron = PatronModel(
            id="ready-patron",
            barcode="READY-P",
            name="Ready Patron",
            email="ready@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(ready_patron)

        ready_hold = HoldModel(
            id="ready-hold",
            book_id=book.id,
            patron_id=ready_patron.id,
            position=1,
            status=HoldStatus.READY.value,
            created_at=now - timedelta(days=3),
            notified_at=now - timedelta(days=2),
            expires_at=now + timedelta(days=5),
        )
        db_session.add(ready_hold)

        # Create PENDING holds
        for i in range(2):
            pending_patron = PatronModel(
                id=f"pending-patron-{i+1}",
                barcode=f"PEND-P-{i+1}",
                name=f"Pending Patron {i+1}",
                email=f"pending{i+1}@test.lib",
                category=PatronCategory.ADULT.value,
                hold_limit=10,
            )
            db_session.add(pending_patron)

            pending_hold = HoldModel(
                id=f"pending-hold-{i+1}",
                book_id=book.id,
                patron_id=pending_patron.id,
                position=i + 2,
                status=HoldStatus.PENDING.value,
                created_at=now - timedelta(days=1-i),
            )
            db_session.add(pending_hold)

        await db_session.commit()

        return {
            "book": book,
            "instance": instance,
            "checkout": checkout,
        }

    @pytest.mark.asyncio
    async def test_return_finds_next_pending_hold_not_ready(self, client, db_session, multiple_ready_holds_scenario):
        """Should find next PENDING hold, not process already-READY holds."""
        data = multiple_ready_holds_scenario

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # Should notify first PENDING patron, not the already-READY one
        assert return_data["next_hold_patron"] == "pending-patron-1"

        # Verify hold statuses
        from sqlalchemy import select
        result = await db_session.execute(
            select(HoldModel).where(
                HoldModel.book_id == data["book"].id
            ).order_by(HoldModel.position)
        )
        holds = result.scalars().all()

        # ready-hold should still be READY (unchanged)
        assert holds[0].id == "ready-hold"
        assert holds[0].status == HoldStatus.READY.value

        # pending-hold-1 should now be READY
        assert holds[1].id == "pending-hold-1"
        assert holds[1].status == HoldStatus.READY.value
        assert holds[1].notified_at is not None

        # pending-hold-2 should still be PENDING
        assert holds[2].id == "pending-hold-2"
        assert holds[2].status == HoldStatus.PENDING.value
        assert holds[2].notified_at is None
