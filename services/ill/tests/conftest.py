"""Test configuration and fixtures for ILL service tests."""

from datetime import datetime, timedelta, UTC
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from ill.main import app
from ill.db import get_session
from ill.models import ILLRequestModel, InboundLoanModel, ILLAuditTrail


# =============================================================================
# Database Fixtures
# =============================================================================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine with in-memory SQLite."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide database session for tests with automatic rollback.

    Also patches the MCP server's async_engine to use the test engine,
    so MCP tools use the same in-memory database.
    """
    async_session_maker = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    # Patch the async_engine in mcp_server module to use test engine
    with patch("ill.mcp_server.async_engine", test_engine):
        async with async_session_maker() as session:
            yield session
            # Automatic rollback on exit


@pytest_asyncio.fixture
async def client(db_session):
    """Test HTTP client with dependency override for database session."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# =============================================================================
# Mock External Library Client
# =============================================================================

@pytest.fixture
def mock_external_library():
    """
    Mock responses from external libraries (e.g., Mastodon Institute).

    This fixture provides configurable responses for:
    - Holdings queries
    - Loan requests
    """

    class MockLibraryClient:
        def __init__(self):
            # Default successful query response
            self.query_response = {
                "isbn": "978-0-MIT-0001",
                "held": True,
                "available_copies": 2,
                "loanable": True,
                "loan_period_days": 28,
            }

            # Default successful loan request response
            self.loan_request_response = {
                "approved": True,
                "request_id": "MAS-ILL-001",
                "estimated_ship_date": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
                "loan_period_days": 28,
            }

        async def query_holdings(self, isbn: str):
            """Mock holdings query."""
            return self.query_response

        async def request_loan(self, isbn: str, patron_ref: str):
            """Mock loan request."""
            return self.loan_request_response

        def set_not_held(self):
            """Configure mock to return book not held."""
            self.query_response["held"] = False
            self.query_response["loanable"] = False
            self.query_response["available_copies"] = 0

        def set_loan_denied(self, reason="no_available_copies"):
            """Configure mock to deny loan request."""
            self.loan_request_response = {
                "approved": False,
                "reason": reason,
                "earliest_available": (datetime.now(UTC) + timedelta(days=14)).isoformat(),
            }

    return MockLibraryClient()


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def sample_ill_request(db_session):
    """Create a sample ILL request in the database."""
    request = ILLRequestModel(
        id="ill-req-001",
        book_id="book-ext-001",
        book_title="Principles of Trunk Engineering",
        isbn="978-0-MIT-0001",
        author="Dr. Mammoth Tuskinson",
        patron_id="patron-001",
        patron_reference="HAN-P-001",
        source_library="mastodon-institute",
        status="requested",
        requested_at=datetime.now(UTC),
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def sample_ill_request_shipped(db_session):
    """Create a sample ILL request in 'shipped' status."""
    request = ILLRequestModel(
        id="ill-req-002",
        book_id="book-ext-002",
        book_title="Advanced Pachyderm Algorithms",
        isbn="978-0-MIT-0002",
        patron_id="patron-002",
        patron_reference="HAN-P-002",
        source_library="mastodon-institute",
        status="shipped",
        requested_at=datetime.now(UTC) - timedelta(days=3),
        shipped_at=datetime.now(UTC) - timedelta(days=1),
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def sample_ill_request_received(db_session):
    """Create a sample ILL request in 'received' status."""
    request = ILLRequestModel(
        id="ill-req-003",
        book_id="book-ext-003",
        book_title="The Ivory Network Protocols",
        isbn="978-0-MIT-0003",
        patron_id="patron-003",
        patron_reference="HAN-P-003",
        source_library="mastodon-institute",
        status="received",
        requested_at=datetime.now(UTC) - timedelta(days=5),
        shipped_at=datetime.now(UTC) - timedelta(days=3),
        received_at=datetime.now(UTC) - timedelta(days=1),
        due_date=datetime.now(UTC) + timedelta(days=27),
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def sample_ill_request_denied(db_session):
    """Create a sample ILL request in 'denied' status."""
    request = ILLRequestModel(
        id="ill-req-004",
        book_id="book-ext-004",
        book_title="Unavailable Book",
        isbn="978-0-MIT-0004",
        patron_id="patron-004",
        patron_reference="HAN-P-004",
        source_library="mastodon-institute",
        status="denied",
        requested_at=datetime.now(UTC) - timedelta(days=2),
        denial_reason="no_available_copies",
        loan_period_days=28,
    )
    db_session.add(request)
    await db_session.commit()
    await db_session.refresh(request)
    return request


@pytest_asyncio.fixture
async def sample_inbound_loan(db_session):
    """Create a sample inbound loan (we're lending to another library)."""
    loan = InboundLoanModel(
        id="inbound-001",
        instance_id="inst-001",
        book_id="book-001",
        requesting_library="mastodon-institute",
        patron_reference="MAS-P-042",  # Opaque - their patron ID
        status="approved",
        approved_at=datetime.now(UTC),
        due_date=datetime.now(UTC) + timedelta(days=28),
        loan_period_days=28,
    )
    db_session.add(loan)
    await db_session.commit()
    await db_session.refresh(loan)
    return loan


@pytest_asyncio.fixture
async def sample_inbound_loan_active(db_session):
    """Create a sample inbound loan in 'active' status (shipped)."""
    loan = InboundLoanModel(
        id="inbound-002",
        instance_id="inst-002",
        book_id="book-002",
        requesting_library="mammoth-valley",
        patron_reference="MV-P-123",
        status="active",
        approved_at=datetime.now(UTC) - timedelta(days=5),
        shipped_at=datetime.now(UTC) - timedelta(days=3),
        due_date=datetime.now(UTC) + timedelta(days=23),
        loan_period_days=28,
    )
    db_session.add(loan)
    await db_session.commit()
    await db_session.refresh(loan)
    return loan


# =============================================================================
# Factory Fixtures
# =============================================================================

@pytest.fixture
def ill_request_factory(db_session):
    """Factory for creating ILL requests with custom attributes."""

    async def create_request(**kwargs):
        defaults = {
            "id": f"ill-req-{datetime.now(UTC).timestamp()}",
            "book_id": "book-ext-default",
            "book_title": "Default Book Title",
            "isbn": "978-0-MIT-9999",
            "patron_id": "patron-default",
            "patron_reference": "HAN-P-999",
            "source_library": "mastodon-institute",
            "status": "requested",
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
def inbound_loan_factory(db_session):
    """Factory for creating inbound loans with custom attributes."""

    async def create_loan(**kwargs):
        defaults = {
            "id": f"inbound-{datetime.now(UTC).timestamp()}",
            "instance_id": "inst-default",
            "book_id": "book-default",
            "requesting_library": "mastodon-institute",
            "patron_reference": "MAS-P-DEFAULT",
            "status": "approved",
            "approved_at": datetime.now(UTC),
            "due_date": datetime.now(UTC) + timedelta(days=28),
            "loan_period_days": 28,
        }
        defaults.update(kwargs)

        loan = InboundLoanModel(**defaults)
        db_session.add(loan)
        await db_session.commit()
        await db_session.refresh(loan)
        return loan

    return create_loan
