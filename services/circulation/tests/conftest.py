"""Pytest configuration and fixtures for circulation service tests."""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timedelta, UTC
from unittest.mock import patch
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport

from circulation.main import app
from circulation.db import get_session
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
    FineReason,
    PATRON_LOAN_RULES,
)


# Test database URL - use in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide an async database session for tests with rollback.

    Also patches the MCP server's async_engine to use the test engine,
    so MCP tools use the same in-memory database.
    """
    async_session_maker = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch the async_engine in mcp_server module to use test engine
    with patch("circulation.mcp_server.async_engine", test_engine):
        async with async_session_maker() as session:
            yield session
            # Rollback is automatic when context exits


@pytest_asyncio.fixture
async def client(db_session):
    """Create a test client with database dependency override."""
    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ============================================================================
# Patron Fixtures
# ============================================================================

@pytest.fixture
def sample_patron_adult():
    """Create a sample adult patron."""
    return PatronModel(
        id="patron-adult-001",
        barcode="HAN-P-001",
        name="Eloise Tuskworth",
        email="eloise.tuskworth@hanno.lib",
        phone="555-0101",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,
        block_reason=None,
    )


@pytest.fixture
def sample_patron_youth():
    """Create a sample youth patron."""
    return PatronModel(
        id="patron-youth-001",
        barcode="HAN-P-002",
        name="Timmy Trunkson",
        email="timmy.trunkson@hanno.lib",
        phone="555-0102",
        category=PatronCategory.YOUTH.value,
        checkout_limit=5,
        hold_limit=5,
        blocked=False,
        block_reason=None,
    )


@pytest.fixture
def sample_patron_staff():
    """Create a sample staff patron."""
    return PatronModel(
        id="patron-staff-001",
        barcode="HAN-STAFF-001",
        name="Dr. Mammoth Wise",
        email="mammoth.wise@hanno.lib",
        phone="555-0103",
        category=PatronCategory.STAFF.value,
        checkout_limit=25,
        hold_limit=15,
        blocked=False,
        block_reason=None,
    )


@pytest.fixture
def sample_patron_researcher():
    """Create a sample researcher patron."""
    return PatronModel(
        id="patron-researcher-001",
        barcode="HAN-R-001",
        name="Prof. Ivory Scholar",
        email="ivory.scholar@hanno.lib",
        phone="555-0104",
        category=PatronCategory.RESEARCHER.value,
        checkout_limit=15,
        hold_limit=10,
        blocked=False,
        block_reason=None,
    )


@pytest.fixture
def sample_patron_blocked():
    """Create a blocked patron with excessive fines."""
    return PatronModel(
        id="patron-blocked-001",
        barcode="HAN-P-BLOCKED",
        name="Delinquent Dumbo",
        email="delinquent.dumbo@hanno.lib",
        phone="555-0199",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=True,
        block_reason="Excessive unpaid fines exceeding $10.00",
    )


# ============================================================================
# Book Instance Fixtures
# ============================================================================

@pytest.fixture
def sample_instance_available():
    """Create an available book instance."""
    return BookInstanceModel(
        id="hanno-book-001-instance-001",
        book_id="hanno-book-001",
        barcode="HAN-ITEM-001",
        call_number="FIC GRE",
        status=InstanceStatus.AVAILABLE.value,
        location="Fiction Wing, Shelf G-12",
        condition="good",
    )


@pytest.fixture
def sample_instance_checked_out():
    """Create a checked out book instance."""
    return BookInstanceModel(
        id="hanno-book-001-instance-002",
        book_id="hanno-book-001",
        barcode="HAN-ITEM-002",
        call_number="FIC GRE",
        status=InstanceStatus.CHECKED_OUT.value,
        location=None,
        condition="good",
    )


# ============================================================================
# Checkout Fixtures
# ============================================================================

@pytest.fixture
def sample_checkout(sample_patron_adult, sample_instance_available):
    """Create an active checkout."""
    now = datetime.now(UTC)
    return CheckoutModel(
        id="checkout-001",
        instance_id=sample_instance_available.id,
        patron_id=sample_patron_adult.id,
        checked_out_at=now,
        due_date=now + timedelta(days=14),
        returned_at=None,
        status=CheckoutStatus.ACTIVE.value,
        renewals_used=0,
        max_renewals=2,
    )


@pytest.fixture
def overdue_checkout(sample_patron_adult, sample_instance_checked_out):
    """Create an overdue checkout (due date in past)."""
    now = datetime.now(UTC)
    return CheckoutModel(
        id="checkout-overdue-001",
        instance_id=sample_instance_checked_out.id,
        patron_id=sample_patron_adult.id,
        checked_out_at=now - timedelta(days=20),
        due_date=now - timedelta(days=6),  # 6 days overdue
        returned_at=None,
        status=CheckoutStatus.OVERDUE.value,
        renewals_used=0,
        max_renewals=2,
    )


@pytest.fixture
def checkout_with_renewals(sample_patron_adult, sample_instance_available):
    """Create a checkout that has been renewed once."""
    now = datetime.now(UTC)
    return CheckoutModel(
        id="checkout-renewed-001",
        instance_id=sample_instance_available.id,
        patron_id=sample_patron_adult.id,
        checked_out_at=now - timedelta(days=14),
        due_date=now + timedelta(days=14),  # Extended by renewal
        returned_at=None,
        status=CheckoutStatus.ACTIVE.value,
        renewals_used=1,
        max_renewals=2,
    )


# ============================================================================
# Hold Fixtures
# ============================================================================

@pytest.fixture
def sample_hold(sample_patron_adult):
    """Create a pending hold."""
    return HoldModel(
        id="hold-001",
        book_id="hanno-book-001",
        patron_id=sample_patron_adult.id,
        position=1,
        status=HoldStatus.PENDING.value,
        created_at=datetime.now(UTC),
        notified_at=None,
        expires_at=None,
    )


@pytest.fixture
def sample_hold_ready(sample_patron_adult):
    """Create a ready hold (item available for pickup)."""
    now = datetime.now(UTC)
    return HoldModel(
        id="hold-ready-001",
        book_id="hanno-book-001",
        patron_id=sample_patron_adult.id,
        position=1,
        status=HoldStatus.READY.value,
        created_at=now - timedelta(days=2),
        notified_at=now,
        expires_at=now + timedelta(days=7),
    )


# ============================================================================
# Fine Fixtures
# ============================================================================

@pytest.fixture
def sample_fine_small(sample_patron_adult, sample_checkout):
    """Create a small unpaid fine ($2.50)."""
    return FineModel(
        id="fine-001",
        patron_id=sample_patron_adult.id,
        checkout_id=sample_checkout.id,
        reason=FineReason.OVERDUE.value,
        amount=2.50,
        description="10 days overdue",
        paid=False,
        paid_at=None,
        waived=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_fine_large(sample_patron_adult, overdue_checkout):
    """Create a large unpaid fine ($10.00 - at blocking threshold)."""
    return FineModel(
        id="fine-large-001",
        patron_id=sample_patron_adult.id,
        checkout_id=overdue_checkout.id,
        reason=FineReason.OVERDUE.value,
        amount=10.00,
        description="40 days overdue (capped at $10.00)",
        paid=False,
        paid_at=None,
        waived=False,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_fine_paid(sample_patron_adult, sample_checkout):
    """Create a paid fine."""
    now = datetime.now(UTC)
    return FineModel(
        id="fine-paid-001",
        patron_id=sample_patron_adult.id,
        checkout_id=sample_checkout.id,
        reason=FineReason.OVERDUE.value,
        amount=1.25,
        description="5 days overdue",
        paid=True,
        paid_at=now,
        waived=False,
        created_at=now - timedelta(days=5),
    )


# ============================================================================
# Seeded Database Fixtures
# ============================================================================

@pytest_asyncio.fixture
async def seeded_db(
    db_session,
    sample_patron_adult,
    sample_patron_youth,
    sample_instance_available,
    sample_instance_checked_out,
):
    """Database with minimal seed data for testing."""
    # Add patrons
    db_session.add(sample_patron_adult)
    db_session.add(sample_patron_youth)

    # Add instances
    db_session.add(sample_instance_available)
    db_session.add(sample_instance_checked_out)

    await db_session.commit()

    return db_session


@pytest_asyncio.fixture
async def seeded_db_with_checkouts(
    seeded_db,
    sample_checkout,
    overdue_checkout,
):
    """Database with patrons, instances, and active checkouts."""
    seeded_db.add(sample_checkout)
    seeded_db.add(overdue_checkout)

    await seeded_db.commit()

    return seeded_db


@pytest_asyncio.fixture
async def seeded_db_with_fines(
    seeded_db_with_checkouts,
    sample_fine_small,
    sample_fine_large,
):
    """Database with patrons, checkouts, and fines."""
    seeded_db_with_checkouts.add(sample_fine_small)
    seeded_db_with_checkouts.add(sample_fine_large)

    await seeded_db_with_checkouts.commit()

    return seeded_db_with_checkouts


# ============================================================================
# Factory Fixtures
# ============================================================================

@pytest.fixture
def patron_factory():
    """Factory for creating test patrons with custom attributes."""
    def _create_patron(**overrides):
        defaults = {
            "id": "test-patron-001",
            "barcode": "TEST-P-001",
            "name": "Test Patron",
            "email": "test.patron@test.lib",
            "phone": "555-0000",
            "category": PatronCategory.ADULT.value,
            "checkout_limit": 10,
            "hold_limit": 10,
            "blocked": False,
            "block_reason": None,
        }
        return PatronModel(**{**defaults, **overrides})
    return _create_patron


@pytest.fixture
def checkout_factory():
    """Factory for creating test checkouts with custom attributes."""
    def _create_checkout(**overrides):
        now = datetime.now(UTC)
        defaults = {
            "id": "test-checkout-001",
            "instance_id": "test-instance-001",
            "patron_id": "test-patron-001",
            "checked_out_at": now,
            "due_date": now + timedelta(days=14),
            "returned_at": None,
            "status": CheckoutStatus.ACTIVE.value,
            "renewals_used": 0,
            "max_renewals": 2,
        }
        return CheckoutModel(**{**defaults, **overrides})
    return _create_checkout


@pytest.fixture
def fine_factory():
    """Factory for creating test fines with custom attributes."""
    def _create_fine(**overrides):
        defaults = {
            "id": "test-fine-001",
            "patron_id": "test-patron-001",
            "checkout_id": "test-checkout-001",
            "reason": FineReason.OVERDUE.value,
            "amount": 2.50,
            "description": "10 days overdue",
            "paid": False,
            "paid_at": None,
            "waived": False,
            "created_at": datetime.now(UTC),
        }
        return FineModel(**{**defaults, **overrides})
    return _create_fine


@pytest.fixture
def hold_factory():
    """Factory for creating test holds with custom attributes."""
    def _create_hold(**overrides):
        defaults = {
            "id": "test-hold-001",
            "book_id": "test-book-001",
            "patron_id": "test-patron-001",
            "position": 1,
            "status": HoldStatus.PENDING.value,
            "created_at": datetime.now(UTC),
            "notified_at": None,
            "expires_at": None,
        }
        return HoldModel(**{**defaults, **overrides})
    return _create_hold
