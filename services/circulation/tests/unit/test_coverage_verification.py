"""Verification tests to ensure coverage tracking works correctly.

These tests explicitly cover basic happy paths to verify coverage collection.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC

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


class TestBasicEndpointCoverage:
    """Basic tests to verify all endpoints are tracked by coverage."""

    @pytest_asyncio.fixture
    async def simple_patron(self, db_session):
        """Create a simple patron."""
        patron = PatronModel(
            id="simple-patron",
            barcode="SIM-P",
            name="Simple Patron",
            email="simple@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            hold_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()
        return patron

    @pytest.mark.asyncio
    async def test_health_endpoint_coverage(self, client):
        """Verify health endpoint is covered."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "circulation"
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_patron_basic_coverage(self, client, simple_patron):
        """Verify GET /patrons/{id} is covered."""
        response = await client.get(f"/patrons/{simple_patron.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["patron"]["id"] == simple_patron.id
        assert data["current_checkouts"] == 0
        assert data["active_holds"] == 0
        assert float(data["fines_owed"]) == 0.0

    @pytest.mark.asyncio
    async def test_get_patron_summary_basic_coverage(self, client, simple_patron):
        """Verify GET /patrons/{id}/summary is covered."""
        response = await client.get(f"/patrons/{simple_patron.id}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["patron"]["id"] == simple_patron.id
        assert len(data["checkouts"]) == 0
        assert len(data["holds"]) == 0
        assert len(data["fines"]) == 0

    @pytest.mark.asyncio
    async def test_get_patron_checkouts_basic_coverage(self, client, simple_patron):
        """Verify GET /patrons/{id}/checkouts is covered."""
        response = await client.get(f"/patrons/{simple_patron.id}/checkouts")
        assert response.status_code == 200
        checkouts = response.json()
        assert isinstance(checkouts, list)
        assert len(checkouts) == 0

    @pytest.mark.asyncio
    async def test_get_patron_holds_basic_coverage(self, client, simple_patron):
        """Verify GET /patrons/{id}/holds is covered."""
        response = await client.get(f"/patrons/{simple_patron.id}/holds")
        assert response.status_code == 200
        holds = response.json()
        assert isinstance(holds, list)
        assert len(holds) == 0

    @pytest.mark.asyncio
    async def test_get_patron_fines_basic_coverage(self, client, simple_patron):
        """Verify GET /patrons/{id}/fines is covered."""
        response = await client.get(f"/patrons/{simple_patron.id}/fines")
        assert response.status_code == 200
        data = response.json()
        assert len(data["fines"]) == 0
        assert float(data["total_owed"]) == 0.0


class TestUtilsCoverage:
    """Tests to improve utils.py coverage."""

    @pytest_asyncio.fixture
    async def patron_and_book(self, db_session):
        """Create patron and book."""
        from sqlmodel import SQLModel, Field, Column
        from sqlalchemy import JSON

        # Inline book model to avoid imports
        class BookModelTest(SQLModel, table=True):
            __tablename__ = "books"
            __table_args__ = {"extend_existing": True}
            id: str = Field(primary_key=True)
            title: str
            author: str
            genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
            stratum: int = 7

        book = BookModelTest(
            id="utils-book",
            title="Utils Test Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="utils-patron",
            barcode="UTILS-P",
            name="Utils Patron",
            email="utils@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        db_session.add(book)
        db_session.add(patron)
        await db_session.commit()

        return {"book": book, "patron": patron}

    @pytest.mark.asyncio
    async def test_get_book_title_coverage(self, client, patron_and_book):
        """Test get_book_title utility through hold placement."""
        data = patron_and_book

        # Place a hold - this should trigger get_book_title
        response = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": data["book"].id,
        })

        assert response.status_code == 200
        hold_data = response.json()

        # Verify book_title was fetched
        assert "book_title" in hold_data
        assert hold_data["book_title"] == "Utils Test Book"

    @pytest.mark.asyncio
    async def test_get_book_title_fallback_coverage(self, client, patron_and_book):
        """Test get_book_title with nonexistent book (fallback path)."""
        data = patron_and_book

        # Place hold on nonexistent book - should trigger fallback in get_book_title
        response = await client.post("/holds", json={
            "patron_id": data["patron"].id,
            "book_id": "nonexistent-book-for-utils",
        })

        assert response.status_code == 200
        hold_data = response.json()

        # Should fallback to book_id when book not found
        assert hold_data["book_title"] == "nonexistent-book-for-utils"

    @pytest.mark.asyncio
    async def test_process_hold_queue_coverage(self, client, db_session, patron_and_book):
        """Test process_hold_queue utility through return workflow."""
        from sqlmodel import SQLModel, Field, Column
        from sqlalchemy import JSON

        class BookModelTest(SQLModel, table=True):
            __tablename__ = "books"
            __table_args__ = {"extend_existing": True}
            id: str = Field(primary_key=True)
            title: str
            author: str
            genres: list[str] = Field(default_factory=list, sa_column=Column(JSON))
            stratum: int = 7

        data = patron_and_book

        # Create instance and checkout
        instance = BookInstanceModel(
            id="utils-inst",
            book_id=data["book"].id,
            barcode="UTILS-ITEM",
            status=InstanceStatus.CHECKED_OUT.value,
            condition="good",
        )

        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id="utils-checkout",
            instance_id=instance.id,
            patron_id=data["patron"].id,
            checked_out_at=now,
            due_date=now + timedelta(days=14),
            status=CheckoutStatus.ACTIVE.value,
        )

        # Create hold
        other_patron = PatronModel(
            id="utils-hold-patron",
            barcode="UHP",
            name="Holder",
            email="holder@test.lib",
            category=PatronCategory.ADULT.value,
            hold_limit=10,
        )

        hold = HoldModel(
            id="utils-hold",
            book_id=data["book"].id,
            patron_id=other_patron.id,
            position=1,
            status=HoldStatus.PENDING.value,
            created_at=now,
        )

        db_session.add(instance)
        db_session.add(checkout)
        db_session.add(other_patron)
        db_session.add(hold)
        await db_session.commit()

        # Return item - should trigger process_hold_queue
        response = await client.post("/returns", json={
            "instance_id": instance.id,
            "dropbox": False,
        })

        assert response.status_code == 200
        return_data = response.json()

        # Verify hold queue was processed
        assert return_data["next_hold_patron"] == other_patron.id
