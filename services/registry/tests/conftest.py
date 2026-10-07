"""Pytest fixtures for registry service tests."""

from datetime import datetime, UTC

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from registry.db import get_session
from registry.main import app
from registry.models import PartnerLibraryModel, LibraryMetricsModel
from registry.a2a_relay import relay_store


TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create in-memory DB engine for registry tests."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """Provide DB session for registry tests."""
    async_session_maker = sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session_maker() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session):
    """HTTP client with dependency override."""

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    relay_store.clear()
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"x-service-token": "dev-token-ai-librarian"},
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
    relay_store.clear()


@pytest_asyncio.fixture
async def seeded_libraries(db_session):
    """Seed partner libraries used in A2A tests."""
    libraries = [
        PartnerLibraryModel(
            code="mastodon-institute",
            name="Mastodon Institute Library",
            display_name="Mastodon Institute",
            status="active",
            member_since=datetime.now(UTC),
        ),
        PartnerLibraryModel(
            code="mammoth-valley",
            name="Mammoth Valley Library",
            display_name="Mammoth Valley",
            status="active",
            member_since=datetime.now(UTC),
        ),
    ]
    for lib in libraries:
        db_session.add(lib)
        db_session.add(
            LibraryMetricsModel(
                library_code=lib.code,
                last_updated=datetime.now(UTC),
            )
        )
    await db_session.commit()
    return libraries
