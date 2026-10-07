"""TDD tests for renewal book_id extraction logic.

This test exposes TODO at:
- routes.py:427 - Simplified book_id extraction from instance_id needs proper implementation
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
from shared.constants import PatronCategory, InstanceStatus, CheckoutStatus, HoldStatus


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


class TestRenewalBookIdExtraction:
    """Tests for proper book_id extraction during renewal (TODO: routes.py:427)."""

    @pytest_asyncio.fixture
    async def setup_renewal_scenario(self, db_session):
        """Create patron, book, instance, and checkout for renewal test."""
        # Create book
        book = BookModelTest(
            id="renewal-book-001",
            title="Renewable Book",
            author="Test Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)

        # Create patron
        patron = PatronModel(
            id="renewal-patron-001",
            barcode="REN-P-001",
            name="Renewal Patron",
            email="renewal@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=False,
        )
        db_session.add(patron)

        # Create instance with complex ID format
        # Testing that we properly extract book_id even with complex instance IDs
        instance = BookInstanceModel(
            id=f"{book.id}-copy-001-special",  # More complex format
            book_id=book.id,
            barcode="REN-ITEM-001",
            call_number="TEST",
            status=InstanceStatus.CHECKED_OUT.value,
            location=None,
            condition="good",
        )
        db_session.add(instance)

        # Create active checkout
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="renewal-checkout-001",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now - timedelta(days=7),
            due_date=now + timedelta(days=7),
            returned_at=None,
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )
        db_session.add(checkout)

        await db_session.commit()

        return {
            "book": book,
            "patron": patron,
            "instance": instance,
            "checkout": checkout,
        }

    @pytest.mark.asyncio
    async def test_renewal_extracts_correct_book_id(self, client, setup_renewal_scenario):
        """Renewal should correctly extract book_id from instance to check for holds."""
        data = setup_renewal_scenario

        # Attempt renewal
        response = await client.post(f"/checkouts/{data['checkout'].id}/renew")

        # Should succeed since no holds are waiting
        assert response.status_code == 200
        renewal_data = response.json()

        # Verify renewal succeeded
        assert renewal_data["checkout"]["id"] == data["checkout"].id
        assert "renewals_remaining" in renewal_data
        assert renewal_data["renewals_remaining"] == 1  # Started with 0, max 2

    @pytest.mark.asyncio
    async def test_renewal_blocked_by_hold_on_correct_book(self, client, db_session, setup_renewal_scenario):
        """Renewal should be blocked if hold exists for the correct book."""
        data = setup_renewal_scenario

        # Create a hold on this book by another patron
        other_patron = PatronModel(
            id="other-patron",
            barcode="OTHER-P",
            name="Other Patron",
            email="other@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(other_patron)

        hold = HoldModel(
            id="blocking-hold",
            book_id=data["book"].id,  # Hold on the actual book
            patron_id=other_patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(hold)
        await db_session.commit()

        # Attempt renewal - should be blocked
        response = await client.post(f"/checkouts/{data['checkout'].id}/renew")

        # Should fail with holds waiting error
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data
        # Should mention holds waiting
        assert "hold" in str(error_data["detail"]).lower() or "HOLDS_WAITING" in str(error_data["detail"])

    @pytest.mark.asyncio
    async def test_renewal_not_blocked_by_hold_on_different_book(self, client, db_session, setup_renewal_scenario):
        """Renewal should NOT be blocked by holds on different books."""
        data = setup_renewal_scenario

        # Create a different book
        other_book = BookModelTest(
            id="different-book",
            title="Different Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(other_book)

        # Create hold on the DIFFERENT book
        other_patron = PatronModel(
            id="other-patron-2",
            barcode="OTHER-P-2",
            name="Other Patron 2",
            email="other2@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(other_patron)

        hold = HoldModel(
            id="non-blocking-hold",
            book_id=other_book.id,  # Hold on DIFFERENT book
            patron_id=other_patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )
        db_session.add(hold)
        await db_session.commit()

        # Attempt renewal - should succeed
        response = await client.post(f"/checkouts/{data['checkout'].id}/renew")

        # Should succeed because hold is on different book
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_renewal_with_various_instance_id_formats(self, client, db_session):
        """Renewal should work with various instance_id formats."""
        # Test different instance_id formats to ensure robust extraction

        formats_to_test = [
            "book-123-instance-001",
            "book-abc-xyz-copy-5",
            "simple-book-inst",
            "book_with_underscores-item-1",
        ]

        for idx, instance_id_format in enumerate(formats_to_test):
            # Extract expected book_id (everything before last hyphen-section)
            # This is what the implementation should do properly
            book_id = f"test-book-{idx:03d}"

            # Create book
            book = BookModelTest(
                id=book_id,
                title=f"Test Book {idx}",
                author="Author",
                genres=["Test"],
                stratum=7,
            )
            db_session.add(book)

            # Create patron
            patron = PatronModel(
                id=f"patron-{idx:03d}",
                barcode=f"P-{idx:03d}",
                name=f"Patron {idx}",
                email=f"patron{idx}@test.lib",
                category=PatronCategory.ADULT.value,
                checkout_limit=10,
            )
            db_session.add(patron)

            # Create instance with format
            instance = BookInstanceModel(
                id=instance_id_format,
                book_id=book_id,
                barcode=f"ITEM-{idx:03d}",
                status=InstanceStatus.CHECKED_OUT.value,
                condition="good",
            )
            db_session.add(instance)

            # Create checkout
            now = datetime.now(UTC)
            checkout = CheckoutModel(
                id=f"checkout-{idx:03d}",
                instance_id=instance_id_format,
                patron_id=patron.id,
                checked_out_at=now,
                due_date=now + timedelta(days=14),
                status=CheckoutStatus.ACTIVE.value,
                renewals_used=0,
                max_renewals=2,
            )
            db_session.add(checkout)

        await db_session.commit()

        # Test renewal for each format
        for idx in range(len(formats_to_test)):
            response = await client.post(f"/checkouts/checkout-{idx:03d}/renew")
            assert response.status_code == 200, f"Failed for format: {formats_to_test[idx]}"


class TestRenewalEdgeCases:
    """Edge cases for renewal logic."""

    @pytest_asyncio.fixture
    async def basic_checkout(self, db_session):
        """Create minimal checkout for edge case testing."""
        book = BookModelTest(
            id="edge-book",
            title="Edge Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="edge-patron",
            barcode="EDGE-P",
            name="Edge Patron",
            email="edge@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        instance = BookInstanceModel(
            id="edge-instance",
            book_id=book.id,
            barcode="EDGE-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="edge-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        return checkout

    @pytest.mark.asyncio
    async def test_renewal_nonexistent_checkout(self, client):
        """Renewal of nonexistent checkout returns 404."""
        response = await client.post("/checkouts/nonexistent-checkout/renew")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_renewal_at_max_renewals(self, client, db_session, basic_checkout):
        """Renewal at max renewals should be rejected."""
        # Update checkout to max renewals
        basic_checkout.renewals_used = 2
        basic_checkout.max_renewals = 2
        db_session.add(basic_checkout)
        await db_session.commit()

        response = await client.post(f"/checkouts/{basic_checkout.id}/renew")
        assert response.status_code == 400
        error = response.json()
        assert "MAX_RENEWALS_REACHED" in str(error["detail"])
