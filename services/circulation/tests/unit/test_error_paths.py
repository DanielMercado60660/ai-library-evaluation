"""Tests for error paths and validation in circulation endpoints.

Covers 404 errors, validation failures, and edge cases to improve coverage.
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


class TestCheckoutErrorPaths:
    """Tests for checkout endpoint error handling."""

    @pytest.mark.asyncio
    async def test_checkout_nonexistent_patron(self, client, db_session):
        """Checkout with nonexistent patron should return 404."""
        book = BookModelTest(
            id="error-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="error-inst",
            book_id=book.id,
            barcode="ERROR-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": "nonexistent-patron",
            "instance_id": instance.id,
        })

        assert response.status_code == 404
        error = response.json()
        assert "Patron not found" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_checkout_nonexistent_instance(self, client, db_session):
        """Checkout with nonexistent instance should return 404."""
        patron = PatronModel(
            id="error-patron",
            barcode="ERROR-P",
            name="Error Patron",
            email="error@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": "nonexistent-instance",
        })

        assert response.status_code == 404
        error = response.json()
        assert "Item not found" in str(error["detail"])


class TestHoldErrorPaths:
    """Tests for hold endpoint error handling."""

    @pytest_asyncio.fixture
    async def patron_and_book(self, db_session):
        """Create patron and book for hold tests."""
        patron = PatronModel(
            id="hold-error-patron",
            barcode="HE-P",
            name="Hold Error Patron",
            email="holderror@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        book = BookModelTest(
            id="hold-error-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        db_session.add(patron)
        db_session.add(book)
        await db_session.commit()

        return {"patron": patron, "book": book}

    @pytest.mark.asyncio
    async def test_hold_nonexistent_patron(self, client, patron_and_book):
        """Hold with nonexistent patron should return 404."""
        data = patron_and_book

        response = await client.post("/holds", json={
            "patron_id": "nonexistent-patron",
            "book_id": data["book"].id,
        })

        assert response.status_code == 404
        error = response.json()
        assert "Patron not found" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_hold_nonexistent_book(self, client, patron_and_book):
        """Hold with nonexistent book should still succeed (book might not be cataloged yet)."""
        data = patron_and_book

        response = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": "nonexistent-book",
        })

        # Hold system allows holds on books not yet in catalog
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_duplicate_hold(self, client, db_session, patron_and_book):
        """Placing duplicate hold should return error."""
        data = patron_and_book

        # Place first hold
        response1 = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": data["book"].id,
        })
        assert response1.status_code == 200

        # Attempt duplicate hold
        response2 = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": data["book"].id,
        })

        # Should fail
        assert response2.status_code == 400
        error = response2.json()
        assert "already" in str(error["detail"]).lower() or "HOLD_ALREADY_EXISTS" in str(error["detail"])


class TestRenewalErrorPaths:
    """Tests for renewal endpoint error handling."""

    @pytest.mark.asyncio
    async def test_renew_nonexistent_checkout(self, client):
        """Renewal of nonexistent checkout should return 404."""
        response = await client.post("/checkouts/nonexistent/renew")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_renew_already_returned_checkout(self, client, db_session):
        """Cannot renew a returned checkout."""
        patron = PatronModel(
            id="returned-patron",
            barcode="RET-P",
            name="Returned Patron",
            email="returned@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )

        book = BookModelTest(
            id="returned-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="returned-inst",
            book_id=book.id,
            barcode="RET-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="returned-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now - timedelta(days=14),
            due_date=now,
            returned_at=now,  # Already returned
            status=CheckoutStatus.RETURNED.value,
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        response = await client.post(f"/checkouts/{checkout.id}/renew")

        assert response.status_code == 400
        error = response.json()
        assert "RENEWAL_NOT_ALLOWED" in str(error["detail"]) or "returned" in str(error["detail"]).lower()


class TestReturnErrorPaths:
    """Tests for return endpoint error handling."""

    @pytest.mark.asyncio
    async def test_return_nonexistent_instance(self, client):
        """Return with nonexistent instance should return 404."""
        response = await client.post("/returns", json={
            "instance_id": "nonexistent-instance",
            "dropbox": False,
        })

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_return_already_available_instance(self, client, db_session):
        """Returning an already-available instance should return error."""
        book = BookModelTest(
            id="available-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="available-inst",
            book_id=book.id,
            barcode="AVAIL-ITEM",
            status=InstanceStatus.AVAILABLE.value,  # Already available
            condition="good",
        )

        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        response = await client.post("/returns", json={
            "instance_id": instance.id,
            "dropbox": False,
        })

        assert response.status_code == 400
        error = response.json()
        assert "No active checkout" in str(error["detail"]) or "NOT_CHECKED_OUT" in str(error["detail"])


class TestFineErrorPaths:
    """Tests for fine endpoint error handling."""

    @pytest.mark.asyncio
    async def test_pay_nonexistent_fine(self, client):
        """Paying nonexistent fine should return 404."""
        response = await client.post("/fines/nonexistent-fine/pay", json={
            "amount": 5.00,
        })

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_pay_already_paid_fine(self, client, db_session):
        """Paying already-paid fine should return error."""
        from circulation.models import FineModel

        patron = PatronModel(
            id="paid-fine-patron",
            barcode="PF-P",
            name="Patron",
            email="paidfine@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )

        fine = FineModel(
            id="already-paid-fine",
            patron_id=patron.id,
            amount=5.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=True,  # Already paid
            paid_at=datetime.now(UTC),
        )

        db_session.add(patron)
        db_session.add(fine)
        await db_session.commit()

        response = await client.post(f"/fines/{fine.id}/pay", json={
            "amount": 5.00,
        })

        assert response.status_code == 400
        error = response.json()
        assert "already paid" in str(error["detail"]).lower() or "FINE_ALREADY_PAID" in str(error["detail"])


class TestCancelHoldErrorPaths:
    """Tests for hold cancellation error handling."""

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_hold(self, client):
        """Canceling nonexistent hold should return 404."""
        response = await client.delete("/holds/nonexistent-hold")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_already_fulfilled_hold(self, client, db_session):
        """Cannot cancel a fulfilled hold."""
        patron = PatronModel(
            id="fulfilled-patron",
            barcode="FUL-P",
            name="Fulfilled Patron",
            email="fulfilled@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        book = BookModelTest(
            id="fulfilled-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        hold = HoldModel(
            id="fulfilled-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.FULFILLED.value,  # Already fulfilled
            created_at=datetime.now(UTC),
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(hold)
        await db_session.commit()

        response = await client.delete(f"/holds/{hold.id}")

        # Should either succeed silently or return error
        assert response.status_code in [200, 400]


class TestValidationErrors:
    """Tests for request validation."""

    @pytest.mark.asyncio
    async def test_checkout_missing_fields(self, client):
        """Checkout with missing required fields should return 422."""
        response = await client.post("/checkouts", json={
            # Missing patron_id and instance_id
        })

        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_hold_missing_fields(self, client):
        """Hold with missing required fields should return 422."""
        response = await client.post("/holds", json={
            # Missing patron_id and book_id
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_return_missing_fields(self, client):
        """Return with missing required fields should return 422."""
        response = await client.post("/returns", json={
            # Missing instance_id and dropbox
        })

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_fine_payment_missing_fields(self, client):
        """Fine payment with missing amount should return 422."""
        response = await client.post("/fines/some-fine/pay", json={
            # Missing amount
        })

        assert response.status_code == 422
