"""Test configuration and fixtures for agent integration tests.

These fixtures provide:
- In-memory SQLite databases for test isolation
- MCP server patching to use test databases
- Sample data for ILL, circulation, and catalog testing
- Factory fixtures for dynamic test data creation
"""

import asyncio
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import AsyncGenerator, Callable
from unittest.mock import patch, AsyncMock
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel


# =============================================================================
# Event Loop Fixture
# =============================================================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create test database engine with in-memory SQLite.

    Creates all tables from all services' models.
    """
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables from all services
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide database session with MCP server patching.

    Patches all service MCP servers to use the test engine,
    ensuring direct tool calls use the same in-memory database.
    """
    async_session_maker = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch ALL service MCP servers to use test engine
    with patch("catalog.mcp_server.async_engine", test_engine):
        with patch("circulation.mcp_server.async_engine", test_engine):
            with patch("ill.mcp_server.async_engine", test_engine):
                async with async_session_maker() as session:
                    yield session
                    # Automatic rollback on exit


# =============================================================================
# ILL Service Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def sample_ill_request(db_session: AsyncSession):
    """Create a sample pending ILL request."""
    from ill.models import ILLRequestModel

    request = ILLRequestModel(
        id=f"ill-req-{uuid4().hex[:8]}",
        book_id="book-ext-001",
        book_title="Principles of Trunk Engineering",
        isbn="978-0-MIT-0001",
        author="Dr. Mammoth Tuskinson",
        patron_id="patron-001",
        patron_reference="HAN-P-001",
        source_library="mastodon-institute",
        status="pending_approval",
        requested_at=datetime.now(UTC),
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def sample_inbound_loan(db_session: AsyncSession):
    """Create a sample pending inbound loan request."""
    from ill.models import InboundLoanModel

    loan = InboundLoanModel(
        id=f"inbound-{uuid4().hex[:8]}",
        instance_id="hanno-book-001-instance-001",
        book_id="hanno-book-001",
        requesting_library="mastodon-institute",
        requesting_library_return_rate=0.92,
        patron_reference="MAS-P-042",
        status="pending",
        loan_period_days=28,
    )
    db_session.add(loan)
    await db_session.commit()
    await db_session.refresh(loan)
    return loan


@pytest.fixture
def ill_request_factory(db_session: AsyncSession) -> Callable:
    """Factory for creating ILL requests with custom attributes."""

    async def create_request(**kwargs) -> "ILLRequestModel":
        from ill.models import ILLRequestModel

        defaults = {
            "id": f"ill-req-{uuid4().hex[:8]}",
            "book_id": "book-ext-default",
            "book_title": "Default Book Title",
            "isbn": "978-0-MIT-9999",
            "patron_id": "patron-default",
            "patron_reference": "HAN-P-999",
            "source_library": "mastodon-institute",
            "status": "pending_approval",
            "requested_at": datetime.now(UTC),
            "loan_period_days": 28,
        }
        defaults.update(kwargs)

        request = ILLRequestModel(**defaults)
        db_session.add(request)
        await db_session.commit()
        await db_session.refresh(request)
        return request

    return create_request


@pytest.fixture
def inbound_loan_factory(db_session: AsyncSession) -> Callable:
    """Factory for creating inbound loans with custom attributes."""

    async def create_loan(**kwargs) -> "InboundLoanModel":
        from ill.models import InboundLoanModel

        defaults = {
            "id": f"inbound-{uuid4().hex[:8]}",
            "instance_id": f"inst-{uuid4().hex[:8]}",
            "book_id": f"book-{uuid4().hex[:8]}",
            "requesting_library": "mastodon-institute",
            "requesting_library_return_rate": 0.90,
            "patron_reference": "MAS-P-DEFAULT",
            "status": "pending",
            "loan_period_days": 28,
        }
        defaults.update(kwargs)

        loan = InboundLoanModel(**defaults)
        db_session.add(loan)
        await db_session.commit()
        await db_session.refresh(loan)
        return loan

    return create_loan


# =============================================================================
# Circulation Service Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def sample_patron_good_standing(db_session: AsyncSession):
    """Create a patron in good standing (eligible for checkout/ILL)."""
    from circulation.models import PatronModel
    from shared.constants import PatronCategory

    patron = PatronModel(
        id="patron-good-001",
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
    db_session.add(patron)
    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def sample_patron_with_fines(db_session: AsyncSession):
    """Create a patron with moderate fines ($5.00)."""
    from circulation.models import PatronModel, FineModel
    from shared.constants import PatronCategory, FineReason

    patron = PatronModel(
        id="patron-fines-001",
        barcode="HAN-P-FINES",
        name="Fined Frank",
        email="fined.frank@hanno.lib",
        phone="555-0102",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,
        block_reason=None,
    )
    db_session.add(patron)

    fine = FineModel(
        id="fine-001",
        patron_id="patron-fines-001",
        checkout_id=None,
        reason=FineReason.OVERDUE.value,
        amount=5.00,
        description="Overdue fines",
        paid=False,
        paid_at=None,
        waived=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(fine)

    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def sample_patron_blocked(db_session: AsyncSession):
    """Create a blocked patron (ineligible)."""
    from circulation.models import PatronModel
    from shared.constants import PatronCategory

    patron = PatronModel(
        id="patron-blocked-001",
        barcode="HAN-P-BLOCKED",
        name="Blocked Bob",
        email="blocked.bob@hanno.lib",
        phone="555-0103",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=True,
        block_reason="Excessive unpaid fines exceeding $10.00",
    )
    db_session.add(patron)
    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest.fixture
def patron_factory(db_session: AsyncSession) -> Callable:
    """Factory for creating patrons with custom attributes."""

    async def create_patron(**kwargs) -> "PatronModel":
        from circulation.models import PatronModel
        from shared.constants import PatronCategory

        defaults = {
            "id": f"patron-{uuid4().hex[:8]}",
            "barcode": f"HAN-P-{uuid4().hex[:8].upper()}",
            "name": "Test Patron",
            "email": "test.patron@test.lib",
            "phone": "555-0000",
            "category": PatronCategory.ADULT.value,
            "checkout_limit": 10,
            "hold_limit": 10,
            "blocked": False,
            "block_reason": None,
        }
        defaults.update(kwargs)

        patron = PatronModel(**defaults)
        db_session.add(patron)
        await db_session.commit()
        await db_session.refresh(patron)
        return patron

    return create_patron


# =============================================================================
# Catalog Service Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def sample_book_with_instances(db_session: AsyncSession):
    """Create a book with multiple instances (varying availability)."""
    from catalog.models import BookModel, BookInstanceModel
    from shared.constants import InstanceStatus

    book = BookModel(
        id="hanno-book-001",
        title="The Great Proboscis",
        author="Herman Melephant",
        isbn="978-0-HAN-0001",
        publisher="Trunk Press",
        publication_year=2020,
        category="Fiction",
        description="A tale of trunks and destiny.",
    )
    db_session.add(book)

    # Create 3 instances: 2 available, 1 checked out
    instances = [
        BookInstanceModel(
            id="hanno-book-001-instance-001",
            book_id="hanno-book-001",
            barcode="HAN-ITEM-001",
            call_number="FIC MEL",
            status=InstanceStatus.AVAILABLE.value,
            location="Fiction Wing, Shelf M-12",
            condition="good",
        ),
        BookInstanceModel(
            id="hanno-book-001-instance-002",
            book_id="hanno-book-001",
            barcode="HAN-ITEM-002",
            call_number="FIC MEL",
            status=InstanceStatus.AVAILABLE.value,
            location="Fiction Wing, Shelf M-12",
            condition="good",
        ),
        BookInstanceModel(
            id="hanno-book-001-instance-003",
            book_id="hanno-book-001",
            barcode="HAN-ITEM-003",
            call_number="FIC MEL",
            status=InstanceStatus.CHECKED_OUT.value,
            location=None,
            condition="good",
        ),
    ]
    for inst in instances:
        db_session.add(inst)

    await db_session.commit()
    await db_session.refresh(book)
    return book


@pytest_asyncio.fixture
async def sample_book_last_copy(db_session: AsyncSession):
    """Create a book with only one instance (last copy scenario)."""
    from catalog.models import BookModel, BookInstanceModel
    from shared.constants import InstanceStatus

    book = BookModel(
        id="hanno-book-rare-001",
        title="Rare Elephant Manuscript",
        author="Ancient Pachyderm",
        isbn="978-0-HAN-RARE",
        publisher="Vintage Trunk Press",
        publication_year=1850,
        category="Rare Books",
        description="A precious single-copy item.",
    )
    db_session.add(book)

    instance = BookInstanceModel(
        id="hanno-book-rare-001-instance-001",
        book_id="hanno-book-rare-001",
        barcode="HAN-RARE-001",
        call_number="RARE ANC",
        status=InstanceStatus.AVAILABLE.value,
        location="Rare Books Room",
        condition="fragile",
    )
    db_session.add(instance)

    await db_session.commit()
    await db_session.refresh(book)
    return book


# =============================================================================
# Mock MCP Tool Fixtures
# =============================================================================

@pytest.fixture
def mock_ill_tools():
    """Create mock ILL MCP tools for unit testing without database."""
    return {
        "get_pending_outbound_queue": AsyncMock(return_value='{"requests": []}'),
        "approve_ill_request": AsyncMock(return_value='{"success": true}'),
        "deny_ill_request": AsyncMock(return_value='{"success": true}'),
        "get_pending_inbound_queue": AsyncMock(return_value='{"loans": []}'),
        "approve_inbound_loan": AsyncMock(return_value='{"success": true}'),
        "deny_inbound_loan": AsyncMock(return_value='{"success": true}'),
    }


@pytest.fixture
def mock_circulation_tools():
    """Create mock circulation MCP tools for unit testing without database."""
    return {
        "check_patron_eligibility": AsyncMock(return_value='{"eligible": true, "total_fines": 0}'),
        "get_patron_summary": AsyncMock(return_value='{"patron_id": "p1", "blocked": false}'),
        "calculate_patron_fines": AsyncMock(return_value='{"total_fines": 0}'),
    }


@pytest.fixture
def mock_catalog_tools():
    """Create mock catalog MCP tools for unit testing without database."""
    return {
        "check_availability": AsyncMock(return_value='{"available": true, "total_copies": 3, "available_copies": 2}'),
        "reserve_instance": AsyncMock(return_value='{"success": true}'),
        "search_books": AsyncMock(return_value='{"books": [], "total": 0}'),
    }


# =============================================================================
# Seeded Database Fixtures (Comprehensive Test Scenarios)
# =============================================================================

@pytest_asyncio.fixture
async def seeded_db_for_ill_approval(
    db_session: AsyncSession,
    sample_patron_good_standing,
    sample_patron_with_fines,
    sample_patron_blocked,
    sample_book_with_instances,
    ill_request_factory,
):
    """Database seeded for ILL approval testing.

    Contains:
    - 3 patrons (good, moderate fines, blocked)
    - 1 book with multiple instances
    - Multiple ILL requests in pending_approval status
    """
    # Create ILL requests for different patron types
    await ill_request_factory(
        id="ill-good-patron",
        patron_id=sample_patron_good_standing.id,
        book_title="Book for Good Patron",
        status="pending_approval",
    )
    await ill_request_factory(
        id="ill-fines-patron",
        patron_id=sample_patron_with_fines.id,
        book_title="Book for Fines Patron",
        status="pending_approval",
    )
    await ill_request_factory(
        id="ill-blocked-patron",
        patron_id=sample_patron_blocked.id,
        book_title="Book for Blocked Patron",
        status="pending_approval",
    )

    return db_session


@pytest_asyncio.fixture
async def seeded_db_for_inbound_loan(
    db_session: AsyncSession,
    sample_book_with_instances,
    sample_book_last_copy,
    inbound_loan_factory,
):
    """Database seeded for inbound loan testing.

    Contains:
    - 1 book with multiple instances (lendable)
    - 1 book with single instance (last copy, restricted)
    - Multiple inbound loan requests
    """
    # Inbound loan for multi-copy book (should approve)
    await inbound_loan_factory(
        id="inbound-multi-copy",
        instance_id="hanno-book-001-instance-001",
        book_id="hanno-book-001",
        requesting_library_return_rate=0.95,
        status="pending",
    )

    # Inbound loan for last copy (should deny or manual review)
    await inbound_loan_factory(
        id="inbound-last-copy",
        instance_id="hanno-book-rare-001-instance-001",
        book_id="hanno-book-rare-001",
        requesting_library_return_rate=0.85,
        status="pending",
    )

    # Inbound loan from unreliable library (should deny)
    await inbound_loan_factory(
        id="inbound-unreliable",
        instance_id="hanno-book-001-instance-002",
        book_id="hanno-book-001",
        requesting_library="unreliable-lib",
        requesting_library_return_rate=0.65,
        status="pending",
    )

    return db_session
