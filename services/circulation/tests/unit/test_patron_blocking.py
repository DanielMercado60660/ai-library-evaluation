"""Unit tests for patron blocking mechanisms.

Tests manual blocking, block reasons, and block enforcement across operations.
Note: Fine-based blocking is tested in test_checkout_rules.py and test_fine_calculations.py
"""

import pytest
import pytest_asyncio
from datetime import datetime, UTC
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import PatronModel, BookInstanceModel, FineModel
from shared.constants import PatronCategory, InstanceStatus


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


class TestManualBlocking:
    """Tests for manually blocking and unblocking patrons."""

    @pytest_asyncio.fixture
    async def patron_for_blocking(self, db_session):
        """Create unblocked patron for blocking tests."""
        patron = PatronModel(
            id="blockable-patron",
            barcode="BLOCK-P",
            name="Blockable Patron",
            email="blockable@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=False,
            block_reason=None,
        )
        db_session.add(patron)
        await db_session.commit()

        return patron

    @pytest.mark.asyncio
    async def test_manual_block_patron(self, client, db_session, patron_for_blocking):
        """Manually blocking a patron should set blocked=True."""
        patron = patron_for_blocking

        # Block the patron
        response = await client.patch(f"/patrons/{patron.id}/block", json={
            "reason": "Suspected fraud",
        })

        assert response.status_code == 200

        # Verify patron is blocked
        from sqlalchemy import select
        result = await db_session.execute(
            select(PatronModel).where(PatronModel.id == patron.id)
        )
        updated_patron = result.scalar_one()

        assert updated_patron.blocked == True
        assert updated_patron.block_reason == "Suspected fraud"

    @pytest.mark.asyncio
    async def test_unblock_patron(self, client, db_session):
        """Unblocking a patron should set blocked=False."""
        # Create blocked patron
        patron = PatronModel(
            id="blocked-patron",
            barcode="BLOCKED-P",
            name="Blocked Patron",
            email="blocked@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=True,
            block_reason="Test block",
        )
        db_session.add(patron)
        await db_session.commit()

        # Unblock the patron
        response = await client.patch(f"/patrons/{patron.id}/unblock")

        assert response.status_code == 200

        # Verify patron is unblocked
        from sqlalchemy import select
        result = await db_session.execute(
            select(PatronModel).where(PatronModel.id == patron.id)
        )
        updated_patron = result.scalar_one()

        assert updated_patron.blocked == False
        assert updated_patron.block_reason is None

    @pytest.mark.asyncio
    async def test_block_reason_persisted(self, client, db_session, patron_for_blocking):
        """Block reason should be stored and retrievable."""
        patron = patron_for_blocking

        # Block with specific reason
        await client.patch(f"/patrons/{patron.id}/block", json={
            "reason": "Lost library card multiple times",
        })

        # Get patron details
        response = await client.get(f"/patrons/{patron.id}")

        assert response.status_code == 200
        patron_data = response.json()

        assert patron_data["patron"]["blocked"] == True
        assert patron_data["patron"]["block_reason"] == "Lost library card multiple times"


class TestBlockedPatronRestrictions:
    """Tests that blocked patrons cannot perform restricted operations."""

    @pytest_asyncio.fixture
    async def blocked_patron_with_book(self, db_session):
        """Create blocked patron, book, and instance."""
        patron = PatronModel(
            id="restricted-patron",
            barcode="REST-P",
            name="Restricted Patron",
            email="restricted@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=True,
            block_reason="Excessive fines",
        )

        book = BookModelTest(
            id="restricted-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="restricted-inst",
            book_id=book.id,
            barcode="REST-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "book": book, "instance": instance}

    @pytest.mark.asyncio
    async def test_blocked_patron_cannot_checkout(self, client, blocked_patron_with_book):
        """Blocked patrons should not be able to check out items."""
        data = blocked_patron_with_book

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "PATRON_BLOCKED" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_blocked_patron_cannot_place_hold(self, client, blocked_patron_with_book):
        """Blocked patrons should not be able to place holds."""
        data = blocked_patron_with_book

        response = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": data["book"].id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "PATRON_BLOCKED" in str(error["detail"]) or "blocked" in str(error["detail"]).lower()


class TestUnblockingAfterFinePayment:
    """Tests automatic unblocking when fine threshold drops below limit."""

    @pytest.mark.asyncio
    async def test_paying_fines_below_threshold_allows_checkout(self, client, db_session):
        """Patron unblocked after paying fines below $10 should be able to checkout."""
        # Create patron blocked by fines
        patron = PatronModel(
            id="fine-payoff-patron",
            barcode="PAYOFF-P",
            name="Payoff Patron",
            email="payoff@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,  # Not manually blocked
        )

        # Create $12.00 in unpaid fines (blocks automatically)
        fine = FineModel(
            id="payoff-fine",
            patron_id=patron.id,
            amount=12.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=False,
            waived=False,
        )

        book = BookModelTest(
            id="payoff-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="payoff-inst",
            book_id=book.id,
            barcode="PAYOFF-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(fine)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        # Verify checkout blocked due to fines
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })
        assert response.status_code == 400  # Blocked by fines

        # Pay the fine
        await client.post(f"/fines/{fine.id}/pay", json={
            "amount": 12.00,
        })

        # Now checkout should succeed
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": instance.id,
        })

        assert response.status_code == 200


class TestPatronSummaryWithBlockStatus:
    """Tests that patron summary includes block status."""

    @pytest.mark.asyncio
    async def test_summary_shows_blocked_status(self, client, db_session):
        """Patron summary should show blocked status and reason."""
        patron = PatronModel(
            id="summary-blocked-patron",
            barcode="SUMM-P",
            name="Summary Patron",
            email="summary@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=True,
            block_reason="Vandalized books",
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.get(f"/patrons/{patron.id}/summary")

        assert response.status_code == 200
        summary = response.json()

        assert summary["patron"]["blocked"] == True
        assert summary["patron"]["block_reason"] == "Vandalized books"

    @pytest.mark.asyncio
    async def test_summary_shows_unblocked_status(self, client, db_session):
        """Patron summary should show unblocked status."""
        patron = PatronModel(
            id="summary-unblocked-patron",
            barcode="SUMM-U-P",
            name="Unblocked Patron",
            email="unblocked@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.get(f"/patrons/{patron.id}/summary")

        assert response.status_code == 200
        summary = response.json()

        assert summary["patron"]["blocked"] == False


class TestBlockReasonValidation:
    """Tests for block reason requirements and validation."""

    @pytest_asyncio.fixture
    async def patron_for_reason_test(self, db_session):
        """Create patron for reason validation tests."""
        patron = PatronModel(
            id="reason-test-patron",
            barcode="REASON-P",
            name="Reason Patron",
            email="reason@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )
        db_session.add(patron)
        await db_session.commit()

        return patron

    @pytest.mark.asyncio
    async def test_block_requires_reason(self, client, patron_for_reason_test):
        """Blocking should require a reason."""
        patron = patron_for_reason_test

        # Attempt to block without reason
        response = await client.patch(f"/patrons/{patron.id}/block", json={})

        # Should fail validation
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_block_rejects_empty_reason(self, client, patron_for_reason_test):
        """Blocking with empty reason should be rejected."""
        patron = patron_for_reason_test

        # Attempt to block with empty reason
        response = await client.patch(f"/patrons/{patron.id}/block", json={
            "reason": "",
        })

        # Should fail validation
        assert response.status_code in [400, 422]
