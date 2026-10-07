"""Unit tests for fine calculation logic.

Tests overdue fine calculations, fine creation, payment processing, and decimal precision.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import PatronModel, BookInstanceModel, CheckoutModel, FineModel
from shared.constants import (
    PatronCategory,
    InstanceStatus,
    CheckoutStatus,
    FINE_RATE_PER_DAY,
    MAX_FINE_BEFORE_BLOCK,
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


class TestOverdueFineCalculation:
    """Tests for calculating overdue fines at $0.25/day."""

    @pytest_asyncio.fixture
    async def overdue_checkout_setup(self, db_session):
        """Create patron, book, instance, and checkout for fine testing."""
        book = BookModelTest(
            id="fine-calc-book",
            title="Fine Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="fine-calc-patron",
            barcode="FINE-P",
            name="Patron",
            email="fine@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="fine-calc-inst",
            book_id=book.id,
            barcode="FINE-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        return {"book": book, "patron": patron, "instance": instance}

    @pytest.mark.asyncio
    async def test_one_day_overdue_fine(self, client, db_session, overdue_checkout_setup):
        """1 day overdue should result in $0.25 fine."""
        data = overdue_checkout_setup

        # Create checkout that's 1 day overdue
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="overdue-1day",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=15),
            due_date=now - timedelta(days=1),  # 1 day overdue
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # Should have created a fine
        assert "fines_incurred" in return_data
        assert float(return_data["fines_incurred"]) == 0.25

    @pytest.mark.asyncio
    async def test_ten_days_overdue_fine(self, client, db_session, overdue_checkout_setup):
        """10 days overdue should result in $2.50 fine."""
        data = overdue_checkout_setup

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="overdue-10days",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=24),
            due_date=now - timedelta(days=10),  # 10 days overdue
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # 10 days * $0.25 = $2.50
        assert float(return_data["fines_incurred"]) == 2.50

    @pytest.mark.asyncio
    async def test_forty_days_overdue_max_fine(self, client, db_session, overdue_checkout_setup):
        """40 days overdue should result in $10.00 fine (40 * 0.25)."""
        data = overdue_checkout_setup

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="overdue-40days",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=54),
            due_date=now - timedelta(days=40),  # 40 days overdue
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        # Return the item
        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # 40 days * $0.25 = $10.00
        assert float(return_data["fines_incurred"]) == 10.00

    @pytest.mark.asyncio
    async def test_decimal_precision(self, client, db_session, overdue_checkout_setup):
        """Fine calculations should maintain decimal precision."""
        data = overdue_checkout_setup

        # Test 3 days overdue: $0.75
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="overdue-3days",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=17),
            due_date=now - timedelta(days=3),
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # Should be exactly $0.75, not rounded
        assert float(return_data["fines_incurred"]) == 0.75


class TestOnTimeReturns:
    """Tests for returns without fines."""

    @pytest_asyncio.fixture
    async def on_time_setup(self, db_session):
        """Create setup for on-time return tests."""
        book = BookModelTest(
            id="ontime-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="ontime-patron",
            barcode="ONTIME-P",
            name="Patron",
            email="ontime@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="ontime-inst",
            book_id=book.id,
            barcode="ONTIME-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        return {"book": book, "patron": patron, "instance": instance}

    @pytest.mark.asyncio
    async def test_return_before_due_date_no_fine(self, client, db_session, on_time_setup):
        """Returning before due date should not create a fine."""
        data = on_time_setup

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="early-return",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=7),
            due_date=now + timedelta(days=7),  # Not due yet
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # No fine should be created
        assert float(return_data.get("fines_incurred", 0)) == 0.0 or float(return_data.get("fines_incurred", 0)) is None

    @pytest.mark.asyncio
    async def test_return_exactly_on_due_date_no_fine(self, client, db_session, on_time_setup):
        """Returning exactly on due date (0 days late) should not create a fine."""
        data = on_time_setup

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="exact-due-return",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=14),
            due_date=now,  # Due exactly now (0 days overdue)
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # 0 days overdue = $0.00 fine
        assert float(return_data.get("fines_incurred", 0)) == 0.0 or float(return_data.get("fines_incurred", 0)) is None


class TestFineCreationAndStorage:
    """Tests for creating and storing fine records."""

    @pytest_asyncio.fixture
    async def fine_storage_setup(self, db_session):
        """Setup for testing fine creation in database."""
        book = BookModelTest(
            id="storage-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="storage-patron",
            barcode="STOR-P",
            name="Patron",
            email="storage@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="storage-inst",
            book_id=book.id,
            barcode="STOR-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        return {"book": book, "patron": patron, "instance": instance}

    @pytest.mark.asyncio
    async def test_fine_created_in_database(self, client, db_session, fine_storage_setup):
        """Fine should be persisted to database with correct patron_id."""
        data = fine_storage_setup

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="fine-db-checkout",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=19),
            due_date=now - timedelta(days=5),  # 5 days overdue
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout)
        await db_session.commit()

        # Return the item (creates fine)
        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Query database for fine
        from sqlalchemy import select
        result = await db_session.execute(
            select(FineModel).where(FineModel.patron_id == data["patron"].id)
        )
        fines = result.scalars().all()

        assert len(fines) == 1
        fine = fines[0]
        assert fine.amount == 1.25  # 5 days * $0.25
        assert fine.paid == False
        assert fine.waived == False

    @pytest.mark.asyncio
    async def test_multiple_overdue_fines_accumulate(self, client, db_session, fine_storage_setup):
        """Multiple overdue returns should create separate fine records."""
        data = fine_storage_setup

        # Create and return first checkout (2 days overdue)
        now = datetime.now(UTC)
        checkout1 = CheckoutModel(
            id="multi-fine-1",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=16),
            due_date=now - timedelta(days=2),
            status=CheckoutStatus.ACTIVE.value,
        )
        db_session.add(checkout1)
        await db_session.commit()

        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Create and return second checkout (3 days overdue)
        # Need to make instance available again first
        from sqlalchemy import select
        instance_result = await db_session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == data["instance"].id)
        )
        instance = instance_result.scalar_one()
        instance.status = InstanceStatus.AVAILABLE.value
        db_session.add(instance)
        await db_session.commit()

        checkout2 = CheckoutModel(
            id="multi-fine-2",
            instance_id=data["instance"].id,
            patron_id=data["patron"].id,
            checked_out_at=now - timedelta(days=17),
            due_date=now - timedelta(days=3),
            status=CheckoutStatus.ACTIVE.value,
        )
        # Update instance status for second checkout
        instance.status = InstanceStatus.CHECKED_OUT.value
        db_session.add(checkout2)
        db_session.add(instance)
        await db_session.commit()

        await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })

        # Check total fines
        result = await db_session.execute(
            select(FineModel).where(FineModel.patron_id == data["patron"].id)
        )
        fines = result.scalars().all()

        assert len(fines) == 2
        total_fines = sum(f.amount for f in fines)
        assert total_fines == 1.25  # (2 * 0.25) + (3 * 0.25) = 1.25


class TestFinePayment:
    """Tests for fine payment processing."""

    @pytest_asyncio.fixture
    async def patron_with_fine(self, db_session):
        """Create patron with existing unpaid fine."""
        patron = PatronModel(
            id="payment-patron",
            barcode="PAY-P",
            name="Payment Patron",
            email="payment@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        fine = FineModel(
            id="payable-fine",
            patron_id=patron.id,
            amount=5.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=False,
            waived=False,
        )

        db_session.add(patron)
        db_session.add(fine)
        await db_session.commit()

        return {"patron": patron, "fine": fine}

    @pytest.mark.asyncio
    async def test_pay_fine(self, client, db_session, patron_with_fine):
        """Paying a fine should mark it as paid."""
        data = patron_with_fine

        response = await client.post(f"/fines/{data['fine'].id}/pay", json={
            "amount": 5.00,
        })

        assert response.status_code == 200

        # Verify fine is marked as paid
        from sqlalchemy import select
        result = await db_session.execute(
            select(FineModel).where(FineModel.id == data["fine"].id)
        )
        fine = result.scalar_one()

        assert fine.paid == True
        assert fine.paid_at is not None

    @pytest.mark.asyncio
    async def test_partial_payment_not_allowed(self, client, patron_with_fine):
        """Partial payments should be rejected."""
        data = patron_with_fine

        # Attempt to pay $3.00 for a $5.00 fine
        response = await client.post(f"/fines/{data['fine'].id}/pay", json={
            "amount": 3.00,
        })

        # Should fail (assuming implementation requires full payment)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_patron_with_paid_fines_not_blocked(self, client, db_session):
        """Patron with only paid fines should not be blocked from checkout."""
        # Create patron with $15 in PAID fines
        patron = PatronModel(
            id="paid-fines-patron",
            barcode="PAID-P",
            name="Paid Patron",
            email="paid@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        fine = FineModel(
            id="paid-fine",
            patron_id=patron.id,
            amount=15.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=True,
            paid_at=datetime.now(UTC),
        )

        book = BookModelTest(
            id="paid-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="paid-inst",
            book_id=book.id,
            barcode="PAID-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(fine)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        # Attempt checkout - should succeed
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })

        assert response.status_code == 200


class TestFineBlockingThreshold:
    """Tests for $10.00 fine blocking threshold."""

    @pytest.mark.asyncio
    async def test_exactly_ten_dollars_blocks_checkout(self, client, db_session):
        """Patron with exactly $10.00 in unpaid fines should be blocked."""
        patron = PatronModel(
            id="threshold-patron",
            barcode="THRESH-P",
            name="Threshold Patron",
            email="thresh@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        fine = FineModel(
            id="threshold-fine",
            patron_id=patron.id,
            amount=10.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=False,
        )

        book = BookModelTest(
            id="thresh-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="thresh-inst",
            book_id=book.id,
            barcode="THRESH-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(fine)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        # Attempt checkout - should be blocked
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "EXCESSIVE_FINES" in str(error["detail"]) or "fine" in str(error["detail"]).lower()

    @pytest.mark.asyncio
    async def test_nine_ninety_nine_does_not_block(self, client, db_session):
        """Patron with $9.99 in unpaid fines should NOT be blocked."""
        patron = PatronModel(
            id="under-thresh-patron",
            barcode="UNDER-P",
            name="Under Threshold Patron",
            email="under@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        fine = FineModel(
            id="under-fine",
            patron_id=patron.id,
            amount=9.99,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=False,
        )

        book = BookModelTest(
            id="under-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="under-inst",
            book_id=book.id,
            barcode="UNDER-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(fine)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        # Attempt checkout - should succeed
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })

        assert response.status_code == 200
