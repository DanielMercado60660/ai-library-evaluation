"""Unit tests for checkout business rules and patron limits.

Tests patron category limits, blocking rules, fine thresholds, and loan periods.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta, UTC
from sqlmodel import SQLModel, Field, Column
from sqlalchemy import JSON

from circulation.models import PatronModel, BookInstanceModel, CheckoutModel, FineModel
from shared.constants import PatronCategory, InstanceStatus, CheckoutStatus


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


class TestPatronCategoryLimits:
    """Tests for checkout limits by patron category."""

    @pytest_asyncio.fixture
    async def setup_limit_test(self, db_session):
        """Create patron and multiple available instances."""
        book = BookModelTest(
            id="limit-book",
            title="Test Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        db_session.add(book)

        # Create 30 instances (more than any category limit)
        instances = []
        for i in range(30):
            instance = BookInstanceModel(
                id=f"limit-inst-{i:03d}",
                book_id=book.id,
                barcode=f"LIMIT-{i:03d}",
                status=InstanceStatus.AVAILABLE.value,
                condition="good",
            )
            db_session.add(instance)
            instances.append(instance)

        await db_session.commit()
        return {"book": book, "instances": instances}

    @pytest.mark.asyncio
    async def test_adult_checkout_limit_10(self, client, db_session, setup_limit_test):
        """Adult patrons should have 10-item checkout limit."""
        data = setup_limit_test

        # Create adult patron
        patron = PatronModel(
            id="adult-patron",
            barcode="ADULT-P",
            name="Adult Patron",
            email="adult@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout 10 items - should all succeed
        for i in range(10):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200

        # 11th checkout should fail
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instances"][10].id,
        })
        assert response.status_code == 400
        error = response.json()
        assert "CHECKOUT_LIMIT_REACHED" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_youth_checkout_limit_5(self, client, db_session, setup_limit_test):
        """Youth patrons should have 5-item checkout limit."""
        data = setup_limit_test

        patron = PatronModel(
            id="youth-patron",
            barcode="YOUTH-P",
            name="Youth Patron",
            email="youth@test.lib",
            category=PatronCategory.YOUTH.value,
            checkout_limit=5,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout 5 items - should succeed
        for i in range(5):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200

        # 6th checkout should fail
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instances"][5].id,
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_staff_checkout_limit_25(self, client, db_session, setup_limit_test):
        """Staff patrons should have 25-item checkout limit."""
        data = setup_limit_test

        patron = PatronModel(
            id="staff-patron",
            barcode="STAFF-P",
            name="Staff Patron",
            email="staff@test.lib",
            category=PatronCategory.STAFF.value,
            checkout_limit=25,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout 25 items
        for i in range(25):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200

        # 26th checkout should fail
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instances"][25].id,
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_researcher_checkout_limit_15(self, client, db_session, setup_limit_test):
        """Researcher patrons should have 15-item checkout limit."""
        data = setup_limit_test

        patron = PatronModel(
            id="researcher-patron",
            barcode="RES-P",
            name="Researcher Patron",
            email="researcher@test.lib",
            category=PatronCategory.RESEARCHER.value,
            checkout_limit=15,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout 15 items
        for i in range(15):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200

        # 16th checkout should fail
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instances"][15].id,
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_restricted_checkout_limit_3(self, client, db_session, setup_limit_test):
        """Restricted patrons should have 3-item checkout limit."""
        data = setup_limit_test

        patron = PatronModel(
            id="restricted-patron",
            barcode="RESTR-P",
            name="Restricted Patron",
            email="restricted@test.lib",
            category=PatronCategory.RESTRICTED.value,
            checkout_limit=3,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout 3 items
        for i in range(3):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200

        # 4th checkout should fail
        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instances"][3].id,
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_exactly_at_limit(self, client, db_session, setup_limit_test):
        """Checkout at exact limit should succeed."""
        data = setup_limit_test

        patron = PatronModel(
            id="edge-patron",
            barcode="EDGE-P",
            name="Edge Patron",
            email="edge@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        # Checkout exactly 10 items
        for i in range(10):
            response = await client.post("/checkouts", json={
                "patron_id": patron.id,
                "instance_id": data["instances"][i].id,
            })
            assert response.status_code == 200


class TestBlockedPatrons:
    """Tests for blocked patron checkout prevention."""

    @pytest_asyncio.fixture
    async def blocked_patron_setup(self, db_session):
        """Create blocked patron and available instance."""
        book = BookModelTest(
            id="block-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="blocked-patron",
            barcode="BLOCK-P",
            name="Blocked Patron",
            email="blocked@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=True,  # Explicitly blocked
        )
        instance = BookInstanceModel(
            id="block-inst",
            book_id=book.id,
            barcode="BLOCK-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "instance": instance}

    @pytest.mark.asyncio
    async def test_blocked_patron_cannot_checkout(self, client, blocked_patron_setup):
        """Blocked patrons should not be able to checkout items."""
        data = blocked_patron_setup

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "PATRON_BLOCKED" in str(error["detail"])


class TestFineThresholdBlocking:
    """Tests for fine-based checkout blocking ($10 threshold)."""

    @pytest_asyncio.fixture
    async def patron_with_fines_setup(self, db_session):
        """Create patron and instance for fine testing."""
        book = BookModelTest(
            id="fine-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="fine-patron",
            barcode="FINE-P",
            name="Fine Patron",
            email="fine@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
            blocked=False,
        )
        instance = BookInstanceModel(
            id="fine-inst",
            book_id=book.id,
            barcode="FINE-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(patron)
        db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "instance": instance}

    @pytest.mark.asyncio
    async def test_patron_with_10_dollar_fines_blocked(self, client, db_session, patron_with_fines_setup):
        """Patron with exactly $10.00 in fines should be blocked."""
        data = patron_with_fines_setup

        # Create $10.00 in unpaid fines
        fine = FineModel(
            id="block-fine",
            patron_id=data["patron"].id,
            amount=10.00,
            reason="Overdue fine",
            created_at=datetime.now(UTC),
            paid=False,
        )
        db_session.add(fine)
        await db_session.commit()

        # Attempt checkout - should be blocked
        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "EXCESSIVE_FINES" in str(error["detail"]) or "fine" in str(error["detail"]).lower()

    @pytest.mark.asyncio
    async def test_patron_with_9_99_fines_allowed(self, client, db_session, patron_with_fines_setup):
        """Patron with $9.99 in fines should be allowed to checkout."""
        data = patron_with_fines_setup

        # Create $9.99 in unpaid fines (just under threshold)
        fine = FineModel(
            id="small-fine",
            patron_id=data["patron"].id,
            amount=9.99,
            reason="Overdue fine",
            created_at=datetime.now(UTC),
            paid=False,
        )
        db_session.add(fine)
        await db_session.commit()

        # Attempt checkout - should succeed
        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_patron_with_paid_fines_allowed(self, client, db_session, patron_with_fines_setup):
        """Patron with paid fines should be allowed to checkout."""
        data = patron_with_fines_setup

        # Create $15.00 in PAID fines (should not block)
        fine = FineModel(
            id="paid-fine",
            patron_id=data["patron"].id,
            amount=15.00,
            reason="Overdue fine",
            created_at=datetime.now(UTC),
            paid=True,
        )
        db_session.add(fine)
        await db_session.commit()

        # Attempt checkout - should succeed
        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_unpaid_fines_accumulate(self, client, db_session, patron_with_fines_setup):
        """Multiple unpaid fines should accumulate toward $10 threshold."""
        data = patron_with_fines_setup

        # Create 3 unpaid fines totaling $10.50
        fines = [
            FineModel(
                id="fine-1",
                patron_id=data["patron"].id,
                amount=4.00,
                reason="Overdue",
                created_at=datetime.now(UTC),
                paid=False,
            ),
            FineModel(
                id="fine-2",
                patron_id=data["patron"].id,
                amount=3.50,
                reason="Overdue",
                created_at=datetime.now(UTC),
                paid=False,
            ),
            FineModel(
                id="fine-3",
                patron_id=data["patron"].id,
                amount=3.00,
                reason="Overdue",
                created_at=datetime.now(UTC),
                paid=False,
            ),
        ]
        for fine in fines:
            db_session.add(fine)
        await db_session.commit()

        # Attempt checkout - should be blocked ($10.50 > $10.00)
        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 400


class TestInstanceAvailability:
    """Tests for item availability validation during checkout."""

    @pytest_asyncio.fixture
    async def availability_test_setup(self, db_session):
        """Create patron and instances with various statuses."""
        book = BookModelTest(
            id="avail-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        patron = PatronModel(
            id="avail-patron",
            barcode="AVAIL-P",
            name="Patron",
            email="avail@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )

        instances = {
            "available": BookInstanceModel(
                id="avail-inst-available",
                book_id=book.id,
                barcode="AVAIL-001",
                status=InstanceStatus.AVAILABLE.value,
                condition="good",
            ),
            "checked_out": BookInstanceModel(
                id="avail-inst-checked-out",
                book_id=book.id,
                barcode="CHECKED-001",
                status=InstanceStatus.CHECKED_OUT.value,
                condition="good",
            ),
            "hold_shelf": BookInstanceModel(
                id="avail-inst-hold",
                book_id=book.id,
                barcode="HOLD-001",
                status=InstanceStatus.HOLD_SHELF.value,
                condition="good",
            ),
            "dropbox": BookInstanceModel(
                id="avail-inst-dropbox",
                book_id=book.id,
                barcode="DROP-001",
                status=InstanceStatus.DROPBOX.value,
                condition="good",
            ),
        }

        db_session.add(book)
        db_session.add(patron)
        for instance in instances.values():
            db_session.add(instance)
        await db_session.commit()

        return {"patron": patron, "instances": instances}

    @pytest.mark.asyncio
    async def test_checkout_available_instance_succeeds(self, client, availability_test_setup):
        """Only AVAILABLE instances should be checkable."""
        data = availability_test_setup

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instances"]["available"].id,
        })

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_checkout_checked_out_instance_fails(self, client, availability_test_setup):
        """Cannot checkout already checked out items."""
        data = availability_test_setup

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instances"]["checked_out"].id,
        })

        assert response.status_code == 400
        error = response.json()
        assert "not available" in str(error["detail"]).lower() or "ITEM_NOT_AVAILABLE" in str(error["detail"])

    @pytest.mark.asyncio
    async def test_checkout_hold_shelf_instance_fails(self, client, availability_test_setup):
        """Cannot checkout items on hold shelf."""
        data = availability_test_setup

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instances"]["hold_shelf"].id,
        })

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_checkout_dropbox_instance_fails(self, client, availability_test_setup):
        """Cannot checkout items in dropbox."""
        data = availability_test_setup

        response = await client.post("/checkouts", json={
            "patron_id": data["patron"].id,
            "instance_id": data["instances"]["dropbox"].id,
        })

        assert response.status_code == 400


class TestLoanPeriods:
    """Tests for loan period calculation by patron category."""

    @pytest_asyncio.fixture
    async def loan_period_setup(self, db_session):
        """Create book and instance for loan period testing."""
        book = BookModelTest(
            id="loan-book",
            title="Book",
            author="Author",
            genres=["Test"],
            stratum=7,
        )
        instance = BookInstanceModel(
            id="loan-inst",
            book_id=book.id,
            barcode="LOAN-ITEM",
            status=InstanceStatus.AVAILABLE.value,
            condition="good",
        )

        db_session.add(book)
        db_session.add(instance)
        await db_session.commit()

        return {"book": book, "instance": instance}

    @pytest.mark.asyncio
    async def test_adult_loan_period_14_days(self, client, db_session, loan_period_setup):
        """Adult patrons should get 14-day loan period."""
        data = loan_period_setup

        patron = PatronModel(
            id="adult-loan",
            barcode="ADULT-LOAN",
            name="Adult",
            email="adult-loan@test.lib",
            category=PatronCategory.ADULT.value,
            checkout_limit=10,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout = response.json()["checkout"]

        # Verify 14-day loan period
        checked_out = datetime.fromisoformat(checkout["checked_out_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(checkout["due_date"].replace("Z", "+00:00"))
        loan_days = (due_date - checked_out).days

        assert loan_days == 14

    @pytest.mark.asyncio
    async def test_youth_loan_period_14_days(self, client, db_session, loan_period_setup):
        """Youth patrons should get 14-day loan period."""
        data = loan_period_setup

        patron = PatronModel(
            id="youth-loan",
            barcode="YOUTH-LOAN",
            name="Youth",
            email="youth-loan@test.lib",
            category=PatronCategory.YOUTH.value,
            checkout_limit=5,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout = response.json()["checkout"]

        checked_out = datetime.fromisoformat(checkout["checked_out_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(checkout["due_date"].replace("Z", "+00:00"))
        loan_days = (due_date - checked_out).days

        assert loan_days == 14

    @pytest.mark.asyncio
    async def test_researcher_loan_period_60_days(self, client, db_session, loan_period_setup):
        """Researcher patrons should get extended 60-day loan period."""
        data = loan_period_setup

        patron = PatronModel(
            id="researcher-loan",
            barcode="RES-LOAN",
            name="Researcher",
            email="res-loan@test.lib",
            category=PatronCategory.RESEARCHER.value,
            checkout_limit=15,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout = response.json()["checkout"]

        checked_out = datetime.fromisoformat(checkout["checked_out_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(checkout["due_date"].replace("Z", "+00:00"))
        loan_days = (due_date - checked_out).days

        assert loan_days == 60

    @pytest.mark.asyncio
    async def test_staff_loan_period_30_days(self, client, db_session, loan_period_setup):
        """Staff patrons should get 30-day loan period."""
        data = loan_period_setup

        patron = PatronModel(
            id="staff-loan",
            barcode="STAFF-LOAN",
            name="Staff",
            email="staff-loan@test.lib",
            category=PatronCategory.STAFF.value,
            checkout_limit=25,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout = response.json()["checkout"]

        checked_out = datetime.fromisoformat(checkout["checked_out_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(checkout["due_date"].replace("Z", "+00:00"))
        loan_days = (due_date - checked_out).days

        assert loan_days == 30

    @pytest.mark.asyncio
    async def test_restricted_loan_period_7_days(self, client, db_session, loan_period_setup):
        """Restricted patrons should get short 7-day loan period."""
        data = loan_period_setup

        patron = PatronModel(
            id="restricted-loan",
            barcode="RESTR-LOAN",
            name="Restricted",
            email="restr-loan@test.lib",
            category=PatronCategory.RESTRICTED.value,
            checkout_limit=3,
        )
        db_session.add(patron)
        await db_session.commit()

        response = await client.post("/checkouts", json={
            "patron_id": patron.id,
            "instance_id": data["instance"].id,
        })

        assert response.status_code == 200
        checkout = response.json()["checkout"]

        checked_out = datetime.fromisoformat(checkout["checked_out_at"].replace("Z", "+00:00"))
        due_date = datetime.fromisoformat(checkout["due_date"].replace("Z", "+00:00"))
        loan_days = (due_date - checked_out).days

        assert loan_days == 7
