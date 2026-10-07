"""Database configuration for the circulation service."""

import os
from sqlmodel import SQLModel, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Database URL from environment or default to SQLite
# Shares database with catalog service
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./library.db")

# Convert to async URL for aiosqlite
if DATABASE_URL.startswith("sqlite:"):
    ASYNC_DATABASE_URL = DATABASE_URL.replace("sqlite:", "sqlite+aiosqlite:")
else:
    ASYNC_DATABASE_URL = DATABASE_URL

# Sync engine (for migrations/setup)
sync_engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
)

# Async engine (for API requests)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in ASYNC_DATABASE_URL else {},
)

# Async session factory
AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


def init_db():
    """Initialize the database tables."""
    SQLModel.metadata.create_all(sync_engine)


async def get_session() -> AsyncSession:
    """Dependency to get an async database session."""
    async with AsyncSessionLocal() as session:
        yield session
