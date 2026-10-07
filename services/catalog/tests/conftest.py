"""Pytest configuration and fixtures for catalog service tests."""

import pytest
import pytest_asyncio
from unittest.mock import patch
from sqlmodel import SQLModel
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from datetime import datetime

from catalog.main import app
from catalog.db import get_session
from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus, ItemCondition


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
    with patch("catalog.mcp_server.async_engine", test_engine):
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


@pytest.fixture
def sample_book():
    """Create a sample book for testing."""
    return BookModel(
        id="hanno-book-001",
        title="Pride and Pachyderm",
        author="Elaphine Greymarch",
        isbn="978-0-HANNO-001",
        genres=["Romance", "Social Commentary"],
        summary="A tale of manners and matrimony in elephant society.",
        publication_year=1813,
        author_dates="1775-1817",
        stratum=7,  # Literary fiction
        publisher="Ivory Stacks Press",
        page_count=432,
        setting_era="Georgian Savanna",
        series=None,
        shelf_location="Fiction Wing, Shelf G-12",
        related_works=["Tusk and Sensibility"],
        notes="First edition, highly sought after",
        illustrations=False,
    )


@pytest.fixture
def sample_book_children():
    """Create a sample children's book for testing."""
    return BookModel(
        id="hanno-book-child-001",
        title="The Very Hungry Elephanterpillar",
        author="Tusk Carle",
        isbn="978-0-HANNO-CHILD-001",
        genres=["Children's", "Picture Book"],
        summary="A tiny elephanterpillar eats through the week.",
        publication_year=1969,
        author_dates="1929-2021",
        stratum=5,  # Children's literature
        publisher="Trunk Publishing",
        page_count=24,
        setting_era="Contemporary",
        series=None,
        shelf_location="Children's Wing, Shelf A-1",
        related_works=[],
        notes="Board book edition available",
        illustrations=True,
        illustrator="Tusk Carle",
        age_range="0-3",
        reading_level="picture book",
    )


@pytest.fixture
def sample_instance_available(sample_book):
    """Create an available book instance."""
    return BookInstanceModel(
        id=f"{sample_book.id}-instance-001",
        book_id=sample_book.id,
        barcode="HAN-ITEM-000001",
        call_number="FIC GRE",
        status=InstanceStatus.AVAILABLE,
        location="Fiction Wing, Shelf G-12",
        condition=ItemCondition.GOOD,
        condition_notes=None,
    )


@pytest.fixture
def sample_instance_checked_out(sample_book):
    """Create a checked out book instance."""
    return BookInstanceModel(
        id=f"{sample_book.id}-instance-002",
        book_id=sample_book.id,
        barcode="HAN-ITEM-000002",
        call_number="FIC GRE",
        status=InstanceStatus.CHECKED_OUT,
        location=None,  # Not on shelf
        condition=ItemCondition.GOOD,
        condition_notes=None,
    )


@pytest.fixture
def sample_instance_hold_shelf(sample_book):
    """Create a book instance on hold shelf."""
    return BookInstanceModel(
        id=f"{sample_book.id}-instance-003",
        book_id=sample_book.id,
        barcode="HAN-ITEM-000003",
        call_number="FIC GRE",
        status=InstanceStatus.HOLD_SHELF,
        location="Hold Shelf",
        condition=ItemCondition.GOOD,
        condition_notes=None,
    )


@pytest_asyncio.fixture
async def seeded_db(db_session, sample_book, sample_book_children):
    """Database with minimal seed data for testing."""
    # Add books
    db_session.add(sample_book)
    db_session.add(sample_book_children)

    # Add instances
    instances = [
        BookInstanceModel(
            id=f"{sample_book.id}-instance-001",
            book_id=sample_book.id,
            barcode="HAN-ITEM-000001",
            call_number="FIC GRE",
            status=InstanceStatus.AVAILABLE,
            location="Fiction Wing, Shelf G-12",
            condition=ItemCondition.GOOD,
        ),
        BookInstanceModel(
            id=f"{sample_book.id}-instance-002",
            book_id=sample_book.id,
            barcode="HAN-ITEM-000002",
            call_number="FIC GRE",
            status=InstanceStatus.CHECKED_OUT,
            location=None,
            condition=ItemCondition.GOOD,
        ),
        BookInstanceModel(
            id=f"{sample_book_children.id}-instance-001",
            book_id=sample_book_children.id,
            barcode="HAN-ITEM-CHILD-001",
            call_number="J CAR",
            status=InstanceStatus.AVAILABLE,
            location="Children's Wing, Shelf A-1",
            condition=ItemCondition.EXCELLENT,
        ),
    ]

    for instance in instances:
        db_session.add(instance)

    await db_session.commit()

    return db_session


@pytest.fixture
def book_factory():
    """Factory for creating test books with custom attributes."""
    def _create_book(**overrides):
        defaults = {
            "id": "test-book-001",
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "978-0-TEST-001",
            "genres": ["Fiction"],
            "summary": "A test book",
            "publication_year": 2024,
            "stratum": 7,
            "publisher": "Test Press",
            "page_count": 200,
            "illustrations": False,
        }
        return BookModel(**{**defaults, **overrides})
    return _create_book


@pytest.fixture
def instance_factory():
    """Factory for creating test book instances with custom attributes."""
    def _create_instance(**overrides):
        defaults = {
            "id": "test-instance-001",
            "book_id": "test-book-001",
            "barcode": "TEST-ITEM-001",
            "call_number": "TEST",
            "status": InstanceStatus.AVAILABLE,
            "location": "Test Shelf",
            "condition": ItemCondition.GOOD,
        }
        return BookInstanceModel(**{**defaults, **overrides})
    return _create_instance
