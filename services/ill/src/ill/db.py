"""Database configuration for the ILL service."""

import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

# Database URL from environment or default
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./library.db")

# Convert to async SQLite URL if using sqlite
if DATABASE_URL.startswith("sqlite:"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:", "sqlite+aiosqlite:")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Async engine for API requests
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    connect_args={"check_same_thread": False} if "sqlite" in ASYNC_DATABASE_URL else {},
)

# Sync engine for database seeding and migrations
from sqlalchemy import create_engine
sync_engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """
    FastAPI dependency for database sessions.

    Yields:
        AsyncSession: Database session for the current request.
    """
    async with AsyncSessionLocal() as session:
        yield session


def init_db():
    """
    Initialize database tables.

    Creates all tables defined in SQLModel metadata if they don't exist.
    Called during application startup.
    """
    from sqlalchemy import create_engine

    # Use sync engine for table creation
    sync_engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    )

    # Import models to register them with SQLModel
    from ill import models  # noqa: F401

    # Create tables
    SQLModel.metadata.create_all(sync_engine)
