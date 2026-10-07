"""Integration tests for complete circulation workflows.

Tests end-to-end patron journeys through the circulation system.
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
    FineModel,
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


class TestCompleteCheckoutFlow:
    """Test complete checkout workflow from patron lookup to return."""

    @pytest_asyncio.fixture
    async def patron_and_book(self, db_session):
        """Create patron and book for checkout flow."""
        patron = PatronModel(
            id="checkout-flow-patron",
            barcode="CF-P",
            name="Checkout Flow Patron",
            email="checkoutflow@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )

        book = BookModelTest(
            id="checkout-flow-book",
            title="Checkout Flow Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        instance = BookInstanceModel(
            id="checkout-flow-inst",
            book_id=book.id,
            barcode="CF-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "book": book, "instance": instance}

    @pytest.mark.asyncio
    async def test_complete_checkout_and_return_flow(self, client, db_session, patron_and_book):
        """Test complete flow: Get patron → Check availability → Checkout → Verify → Return."""
        data = patron_and_book

        # Step 1: Get patron details
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        assert patron_response.status_code == 200
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 0
        assert float(patron_data["fines_owed"]) == 0.0

        # Step 2: Verify instance is available
        from sqlalchemy import select
        result = await db_session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == data["instance"].id)
        )
        instance = result.scalar_one()
        assert instance.status == InstanceStatus.AVAILABLE.value

        # Step 3: Checkout the item
        checkout_response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })
        assert checkout_response.status_code == 200
        checkout_data = checkout_response.json()
        checkout_id = checkout_data["checkout"]["id"]

        # Step 4: Verify patron now has 1 checkout
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 1

        # Step 5: Verify instance is checked out
        await db_session.refresh(instance)
        assert instance.status == InstanceStatus.CHECKED_OUT.value

        # Step 6: Return the item (on time, no fines)
        return_response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })
        assert return_response.status_code == 200
        return_data = return_response.json()
        assert float(return_data["fines_incurred"]) == 0.0

        # Step 7: Verify patron has 0 checkouts
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 0
        assert float(patron_data["fines_owed"]) == 0.0

        # Step 8: Verify instance is available again
        await db_session.refresh(instance)
        assert instance.status == InstanceStatus.AVAILABLE.value


class TestOverdueFlow:
    """Test overdue checkout flow with fine calculation and payment."""

    @pytest_asyncio.fixture
    async def overdue_checkout(self, db_session):
        """Create overdue checkout scenario."""
        patron = PatronModel(
            id="overdue-patron",
            barcode="OD-P",
            name="Overdue Patron",
            email="overdue@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )

        book = BookModelTest(
            id="overdue-book",
            title="Overdue Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        instance = BookInstanceModel(
            id="overdue-inst",
            book_id=book.id,
            barcode="OD-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        # Checkout 20 days ago, due 6 days ago (14 day loan period)
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="overdue-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now - timedelta(days=20),
            due_date=now - timedelta(days=6),  # 6 days overdue
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        return {"patron": patron, "instance": instance, "checkout": checkout}

    @pytest.mark.asyncio
    async def test_overdue_return_creates_fine_then_pay(self, client, overdue_checkout):
        """Test overdue return → Fine created → Pay fine → Patron clear."""
        data = overdue_checkout

        # Step 1: Verify patron has 0 fines before return
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert float(patron_data["fines_owed"]) == 0.0

        # Step 2: Return overdue item (6 days late = $1.50)
        return_response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })
        assert return_response.status_code == 200
        return_data = return_response.json()
        assert float(return_data["fines_incurred"]) == 1.50  # 6 days * $0.25

        # Step 3: Verify patron now has $1.50 in fines
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert float(patron_data["fines_owed"]) == 1.50

        # Step 4: Get fine details
        fines_response = await client.get(f"/patrons/{data['patron'].id}/fines")
        fines_data = fines_response.json()
        assert len(fines_data["fines"]) == 1
        fine_id = fines_data["fines"][0]["id"]
        assert float(fines_data["fines"][0]["amount"]) == 1.50
        assert fines_data["fines"][0]["paid"] == False

        # Step 5: Pay the fine
        pay_response = await client.post(f"/fines/{fine_id}/pay", json={
            "amount": 1.50,
        })
        assert pay_response.status_code == 200

        # Step 6: Verify fine is no longer in unpaid fines list (endpoint filters paid fines)
        fines_response = await client.get(f"/patrons/{data['patron'].id}/fines")
        fines_data = fines_response.json()
        assert len(fines_data["fines"]) == 0  # Paid fines are filtered out
        assert float(fines_data["total_owed"]) == 0.0

        # Step 7: Verify patron summary shows 0 owed
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert float(patron_data["fines_owed"]) == 0.0


class TestHoldFlow:
    """Test hold placement, queue management, and fulfillment."""

    @pytest_asyncio.fixture
    async def hold_scenario(self, db_session):
        """Create scenario for hold workflow."""
        # Patron who has the book checked out
        patron1 = PatronModel(
            id="hold-patron-1",
            barcode="HP1-P",
            name="Patron 1",
            email="patron1@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )

        # Patron who will place a hold
        patron2 = PatronModel(
            id="hold-patron-2",
            barcode="HP2-P",
            name="Patron 2",
            email="patron2@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        book = BookModelTest(
            id="hold-book",
            title="Hold Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        instance = BookInstanceModel(
            id="hold-inst",
            book_id=book.id,
            barcode="HOLD-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="hold-checkout",
            instance_id=instance.id,
            patron_id=patron1.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
        )

        db_session.add(patron1)
        db_session.add(patron2)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        return {
            "patron1": patron1,
            "patron2": patron2,
            "book": book,
            "instance": instance,
            "checkout": checkout,
        }

    @pytest.mark.asyncio
    async def test_hold_placement_and_fulfillment(self, client, db_session, hold_scenario):
        """Test: Place hold → Item returned → Hold ready → Check hold status."""
        data = hold_scenario

        # Step 1: Patron 2 places hold on checked out book
        hold_response = await client.post("/holds", json={
            "patron_id": data["patron2"].id,
            "book_id": data["book"].id,
        })
        assert hold_response.status_code == 200
        hold_data = hold_response.json()
        hold_id = hold_data["hold"]["id"]
        assert hold_data["hold"]["status"] == HoldStatus.PENDING.value
        assert hold_data["hold"]["position"] == 1

        # Step 2: Verify patron has 1 active hold
        holds_response = await client.get(f"/patrons/{data['patron2'].id}/holds")
        holds = holds_response.json()
        assert len(holds) == 1

        # Step 3: Patron 1 returns the item
        return_response = await client.post("/returns", json={
            "instance_id": data["instance"].id,
            "dropbox": False,
        })
        assert return_response.status_code == 200
        return_data = return_response.json()
        assert return_data["next_hold_patron"] == data["patron2"].id

        # Step 4: Verify hold is now READY
        hold_detail = await client.get(f"/holds/{hold_id}")
        assert hold_detail.status_code == 200
        hold_info = hold_detail.json()
        assert hold_info["status"] == HoldStatus.READY.value
        assert "notified_at" in hold_info
        assert "expires_at" in hold_info

        # Step 5: Verify instance is on hold shelf
        from sqlalchemy import select
        result = await db_session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == data["instance"].id)
        )
        instance = result.scalar_one()
        assert instance.status == InstanceStatus.HOLD_SHELF.value


class TestBlockAndUnblockFlow:
    """Test patron blocking due to excessive fines and unblocking after payment."""

    @pytest_asyncio.fixture
    async def patron_for_blocking(self, db_session):
        """Create patron with setup for blocking scenario."""
        patron = PatronModel(
            id="block-flow-patron",
            barcode="BF-P",
            name="Block Flow Patron",
            email="blockflow@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )

        book = BookModelTest(
            id="block-flow-book",
            title="Block Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        instance = BookInstanceModel(
            id="block-flow-inst",
            book_id=book.id,
            barcode="BF-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "book": book, "instance": instance}

    @pytest.mark.asyncio
    async def test_excessive_fines_block_then_unblock(self, client, db_session, patron_for_blocking):
        """Test: Accumulate $12 fines → Blocked from checkout → Pay fines → Unblocked."""
        data = patron_for_blocking

        # Step 1: Create $12 in unpaid fines (exceeds $10 threshold)
        fine = FineModel(
            id="blocking-fine",
            patron_id=data["patron"].id,
            amount=12.00,
            reason="overdue",
            created_at=datetime.now(UTC),
            paid=False,
            waived=False,
        )
        db_session.add(fine)
        await db_session.commit()

        # Step 2: Verify patron shows $12 owed
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert float(patron_data["fines_owed"]) == 12.00

        # Step 3: Attempt checkout - should be blocked
        checkout_response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })
        assert checkout_response.status_code == 400
        error = checkout_response.json()
        assert "fines" in str(error["detail"]).lower() or "PATRON_BLOCKED" in str(error["detail"])

        # Step 4: Pay the fine
        pay_response = await client.post(f"/fines/{fine.id}/pay", json={
            "amount": 12.00,
        })
        assert pay_response.status_code == 200

        # Step 5: Verify patron now has 0 owed
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert float(patron_data["fines_owed"]) == 0.0

        # Step 6: Checkout should now succeed
        checkout_response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })
        assert checkout_response.status_code == 200


class TestCheckoutLimitFlow:
    """Test checkout limit enforcement and recovery."""

    @pytest_asyncio.fixture
    async def patron_at_limit(self, db_session):
        """Create patron with 5 checkouts (at limit for youth)."""
        patron = PatronModel(
            id="limit-patron",
            barcode="LIM-P",
            name="Limit Patron",
            email="limit@test.lib",
            category=PatronCategory.YOUTH.value,  # Limit: 5
            checkout_limit=5,
            blocked=False,
        )

        book = BookModelTest(
            id="limit-book-base",
            title="Limit Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        # Create 5 instances, all checked out
        instances = []
        checkouts = []
        now = datetime.now(UTC)

        for i in range(1, 6):
            inst = BookInstanceModel(
                id=f"limit-inst-{i}",
                book_id=book.id,
                barcode=f"LIM-ITEM-{i}",
                status=InstanceStatus.CHECKED_OUT.value,
                condition="good",
            )
            instances.append(inst)

            checkout = CheckoutModel(
                id=f"limit-checkout-{i}",
                instance_id=inst.id,
                patron_id=patron.id,
                checked_out_at=now,
                due_date=now + timedelta(days=14),
                status=CheckoutStatus.ACTIVE.value,
                renewals_used=0,
                max_renewals=2,
            )
            checkouts.append(checkout)

        # Create one more available instance
        extra_instance = BookInstanceModel(
            id="limit-inst-extra",
            book_id=book.id,
            barcode="LIM-ITEM-EXTRA",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(patron)
        db_session.add(book)
        for inst in instances:
            db_session.add(inst)
        for co in checkouts:
            db_session.add(co)
        db_session.add(extra_instance)
        await db_session.commit()

        return {
            "patron": patron,
            "book": book,
            "instances": instances,
            "extra_instance": extra_instance,
        }

    @pytest.mark.asyncio
    async def test_checkout_limit_enforcement_and_recovery(self, client, patron_at_limit):
        """Test: At limit → Checkout fails → Return one → Checkout succeeds."""
        data = patron_at_limit

        # Step 1: Verify patron has 5 checkouts
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 5

        # Step 2: Attempt to checkout 6th item - should fail
        checkout_response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["extra_instance"].id,
        })
        assert checkout_response.status_code == 400
        error = checkout_response.json()
        assert "limit" in str(error["detail"]).lower() or "CHECKOUT_LIMIT_EXCEEDED" in str(error["detail"])

        # Step 3: Return one item
        return_response = await client.post("/returns", json={
            "instance_id": data["instances"][0].id,
            "dropbox": False,
        })
        assert return_response.status_code == 200

        # Step 4: Verify patron now has 4 checkouts
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 4

        # Step 5: Checkout should now succeed
        checkout_response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["extra_instance"].id,
        })
        assert checkout_response.status_code == 200

        # Step 6: Verify patron is back at limit
        patron_response = await client.get(f"/patrons/{data['patron'].id}")
        patron_data = patron_response.json()
        assert patron_data["current_checkouts"] == 5


class TestRenewalFlow:
    """Test checkout renewal workflow."""

    @pytest_asyncio.fixture
    async def renewable_checkout(self, db_session):
        """Create checkout eligible for renewal."""
        patron = PatronModel(
            id="renewal-patron",
            barcode="REN-P",
            name="Renewal Patron",
            email="renewal@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )

        book = BookModelTest(
            id="renewal-book",
            title="Renewal Book",
            author="Test Author",
            genres=["Fiction"],
            stratum=5,
        )

        instance = BookInstanceModel(
            id="renewal-inst",
            book_id=book.id,
            barcode="REN-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="renewal-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now - timedelta(days=7),
            due_date=now + timedelta(days=7),  # Due in 7 days
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        return {"patron": patron, "checkout": checkout, "instance": instance}

    @pytest.mark.asyncio
    async def test_renewal_extends_due_date(self, client, db_session, renewable_checkout):
        """Test: Renew checkout → Due date reset to new period → Renewal count incremented."""
        data = renewable_checkout

        # Step 1: Get original checkout details
        checkout_response = await client.get(f"/checkouts/{data['checkout'].id}")
        original_checkout = checkout_response.json()
        original_due_date = datetime.fromisoformat(original_checkout["due_date"].replace("Z", "+00:00"))

        # Step 2: Renew the checkout
        renew_response = await client.post(f"/checkouts/{data['checkout'].id}/renew")
        assert renew_response.status_code == 200
        renewed_checkout = renew_response.json()

        # Step 3: Verify due date is reset to 14 days from now (not extended from original)
        new_due_date = datetime.fromisoformat(renewed_checkout["new_due_date"].replace("Z", "+00:00"))
        now = datetime.now(UTC)
        expected_due_date = now + timedelta(days=14)
        # Allow 2 second tolerance for processing time
        assert abs((new_due_date - expected_due_date).total_seconds()) < 2

        # Verify new due date is after original (patron gets more time)
        assert new_due_date > original_due_date

        # Step 4: Renew again (2nd renewal)
        renew_response2 = await client.post(f"/checkouts/{data['checkout'].id}/renew")
        assert renew_response2.status_code == 200

        # Step 5: Attempt 3rd renewal - should fail (max 2 renewals)
        renew_response3 = await client.post(f"/checkouts/{data['checkout'].id}/renew")
        assert renew_response3.status_code == 400
        error = renew_response3.json()
        assert "renewal" in str(error["detail"]).lower() or "MAX_RENEWALS_REACHED" in str(error["detail"])
