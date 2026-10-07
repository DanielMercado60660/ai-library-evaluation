"""Tests to fill coverage gaps in circulation API endpoints.

Covers GET endpoints and edge cases not tested elsewhere.
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


class TestPatronEndpoints:
    """Tests for patron GET endpoints."""

    @pytest_asyncio.fixture
    async def patron_with_activity(self, db_session):
        """Create patron with checkouts, holds, and fines."""
        patron = PatronModel(
            id="active-patron",
            barcode="ACTIVE-P",
            name="Active Patron",
            email="active@test.lib",
            phone="555-0100",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
            blocked=False,
        )

        book = BookModelTest(
            id="active-book",
            title="Active Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="active-inst",
            book_id=book.id,
            barcode="ACTIVE-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="active-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
        )

        hold = HoldModel(
            id="active-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=now,
        )

        fine = FineModel(
            id="active-fine",
            patron_id=patron.id,
            amount=2.50,
            reason="overdue",
            created_at=now,
            paid=False,
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        db_session.add(hold)
        db_session.add(fine)
        await db_session.commit()

        return {
            "patron": patron,
            "book": book,
            "instance": instance,
            "checkout": checkout,
            "hold": hold,
            "fine": fine,
        }

    @pytest.mark.asyncio
    async def test_get_patron_details(self, client, patron_with_activity):
        """GET /patrons/{id} should return patron with activity counts."""
        data = patron_with_activity

        response = await client.get(f"/patrons/{data['patron'].id}")

        assert response.status_code == 200
        patron_data = response.json()

        assert patron_data["patron"]["id"] == data["patron"].id
        assert patron_data["patron"]["name"] == "Active Patron"
        assert patron_data["patron"]["email"] == "active@test.lib"
        assert patron_data["current_checkouts"] == 1
        assert patron_data["active_holds"] == 1
        assert float(patron_data["fines_owed"]) == 2.50

    @pytest.mark.asyncio
    async def test_get_patron_summary(self, client, patron_with_activity):
        """GET /patrons/{id}/summary should return detailed activity."""
        data = patron_with_activity

        response = await client.get(f"/patrons/{data['patron'].id}/summary")

        assert response.status_code == 200
        summary = response.json()

        assert summary["patron"]["id"] == data["patron"].id
        assert len(summary["checkouts"]) == 1
        assert len(summary["holds"]) == 1
        assert len(summary["fines"]) == 1

    @pytest.mark.asyncio
    async def test_get_nonexistent_patron(self, client):
        """GET /patrons/{id} with invalid ID should return 404."""
        response = await client.get("/patrons/nonexistent-patron")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_patron_checkouts_list(self, client, patron_with_activity):
        """GET /patrons/{id}/checkouts should list all checkouts."""
        data = patron_with_activity

        response = await client.get(f"/patrons/{data['patron'].id}/checkouts")

        assert response.status_code == 200
        checkouts = response.json()

        assert len(checkouts) == 1
        assert checkouts[0]["id"] == data["checkout"].id

    @pytest.mark.asyncio
    async def test_get_patron_holds_list(self, client, patron_with_activity):
        """GET /patrons/{id}/holds should list all holds."""
        data = patron_with_activity

        response = await client.get(f"/patrons/{data['patron'].id}/holds")

        assert response.status_code == 200
        holds = response.json()

        assert len(holds) == 1
        assert holds[0]["id"] == data["hold"].id

    @pytest.mark.asyncio
    async def test_get_patron_fines_list(self, client, patron_with_activity):
        """GET /patrons/{id}/fines should list all fines."""
        data = patron_with_activity

        response = await client.get(f"/patrons/{data['patron'].id}/fines")

        assert response.status_code == 200
        fines_data = response.json()

        assert len(fines_data["fines"]) == 1
        assert fines_data["fines"][0]["id"] == data["fine"].id
        assert float(fines_data["total_owed"]) == 2.50


class TestCheckoutEndpoints:
    """Tests for checkout GET endpoints."""

    @pytest_asyncio.fixture
    async def existing_checkout(self, db_session):
        """Create checkout for testing."""
        patron = PatronModel(
            id="checkout-patron",
            barcode="CO-P",
            name="Checkout Patron",
            email="checkout@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )

        book = BookModelTest(
            id="checkout-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        instance = BookInstanceModel(
            id="checkout-inst",
            book_id=book.id,
            barcode="CO-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="get-checkout",
            instance_id=instance.id,
            patron_id=patron.id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(instance)
        db_session.add(checkout)
        await db_session.commit()

        return {"patron": patron, "book": book, "instance": instance, "checkout": checkout}

    @pytest.mark.asyncio
    async def test_get_checkout_details(self, client, existing_checkout):
        """GET /checkouts/{id} should return checkout details."""
        data = existing_checkout

        response = await client.get(f"/checkouts/{data['checkout'].id}")

        assert response.status_code == 200
        checkout_data = response.json()

        assert checkout_data["id"] == data["checkout"].id
        assert checkout_data["patron_id"] == data["patron"].id
        assert checkout_data["instance_id"] == data["instance"].id
        assert checkout_data["status"] == CheckoutStatus.ACTIVE.value

    @pytest.mark.asyncio
    async def test_get_nonexistent_checkout(self, client):
        """GET /checkouts/{id} with invalid ID should return 404."""
        response = await client.get("/checkouts/nonexistent-checkout")

        assert response.status_code == 404


class TestHoldEndpoints:
    """Tests for hold GET endpoints."""

    @pytest_asyncio.fixture
    async def existing_hold(self, db_session):
        """Create hold for testing."""
        patron = PatronModel(
            id="hold-patron",
            barcode="HOLD-P",
            name="Hold Patron",
            email="hold@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        book = BookModelTest(
            id="hold-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )

        hold = HoldModel(
            id="get-hold",
            book_id=book.id,
            patron_id=patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=datetime.now(UTC),
        )

        db_session.add(patron)
        db_session.add(book)
        db_session.add(hold)
        await db_session.commit()

        return {"patron": patron, "book": book, "hold": hold}

    @pytest.mark.asyncio
    async def test_get_hold_details(self, client, existing_hold):
        """GET /holds/{id} should return hold details."""
        data = existing_hold

        response = await client.get(f"/holds/{data['hold'].id}")

        assert response.status_code == 200
        hold_data = response.json()

        assert hold_data["id"] == data["hold"].id
        assert hold_data["patron_id"] == data["patron"].id
        assert hold_data["book_id"] == data["book"].id
        assert hold_data["status"] == HoldStatus.PENDING.value

    @pytest.mark.asyncio
    async def test_get_nonexistent_hold(self, client):
        """GET /holds/{id} with invalid ID should return 404."""
        response = await client.get("/holds/nonexistent-hold")

        assert response.status_code == 404


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """GET /health should return service status."""
        response = await client.get("/health")

        assert response.status_code == 200
        health = response.json()

        assert health["service"] == "circulation"
        assert health["status"] == "healthy"


class TestEdgeCasesAndErrors:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_patron_with_no_activity(self, client, db_session):
        """Patron with no checkouts/holds/fines should return empty lists."""
        patron = PatronModel(
            id="empty-patron",
            barcode="EMPTY-P",
            name="Empty Patron",
            email="empty@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Get patron details
        response = await client.get(f"/patrons/{patron.id}")
        assert response.status_code == 200
        patron_data = response.json()
        assert patron_data["current_checkouts"] == 0
        assert patron_data["active_holds"] == 0
        assert float(patron_data["fines_owed"]) == 0.0

        # Get patron summary
        response = await client.get(f"/patrons/{patron.id}/summary")
        assert response.status_code == 200
        summary = response.json()
        assert len(summary["checkouts"]) == 0
        assert len(summary["holds"]) == 0
        assert len(summary["fines"]) == 0

    @pytest.mark.asyncio
    async def test_get_checkouts_for_patron_with_none(self, client, db_session):
        """GET /patrons/{id}/checkouts with no checkouts should return empty list."""
        patron = PatronModel(
            id="no-checkout-patron",
            barcode="NCO-P",
            name="No Checkout Patron",
            email="nocheckout@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.get(f"/patrons/{patron.id}/checkouts")

        assert response.status_code == 200
        checkouts = response.json()
        assert len(checkouts) == 0

    @pytest.mark.asyncio
    async def test_get_holds_for_patron_with_none(self, client, db_session):
        """GET /patrons/{id}/holds with no holds should return empty list."""
        patron = PatronModel(
            id="no-hold-patron",
            barcode="NHO-P",
            name="No Hold Patron",
            email="nohold@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.get(f"/patrons/{patron.id}/holds")

        assert response.status_code == 200
        holds = response.json()
        assert len(holds) == 0

    @pytest.mark.asyncio
    async def test_get_fines_for_patron_with_none(self, client, db_session):
        """GET /patrons/{id}/fines with no fines should return empty list."""
        patron = PatronModel(
            id="no-fine-patron",
            barcode="NFI-P",
            name="No Fine Patron",
            email="nofine@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.get(f"/patrons/{patron.id}/fines")

        assert response.status_code == 200
        fines = response.json()
        assert len(fines["fines"]) == 0
        assert float(fines["total_owed"]) == 0.0
