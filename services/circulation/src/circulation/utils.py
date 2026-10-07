"""Utility functions for the circulation service."""

from datetime import datetime, timedelta, UTC
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from circulation.models import HoldModel
from shared.constants import HoldStatus, DEFAULT_HOLD_EXPIRY_DAYS


async def get_book_title(session: AsyncSession, book_id: str) -> str:
    """Get book title from catalog by book_id.

    Args:
        session: Async database session
        book_id: ID of the book to look up

    Returns:
        Book title if found, otherwise returns the book_id as fallback
    """
    try:
        # Query books table to get title
        # Note: In production, this would be a cross-service call to catalog API
        # For now, we share the database, so we can query directly
        result = await session.execute(
            select(text("title")).select_from(text("books")).where(text(f"id = '{book_id}'"))
        )
        row = result.first()

        if row:
            return row[0]
        else:
            # Book not found, return book_id as fallback
            return book_id

    except Exception:
        # On any error, fallback to returning book_id
        return book_id


async def process_hold_queue(session: AsyncSession, book_id: str) -> str | None:
    """Process hold queue for a book when an item becomes available.

    Finds the next pending hold and transitions it to ready status.
    Sets notification and expiry dates.

    Args:
        session: Async database session
        book_id: ID of the book that became available

    Returns:
        Patron ID of the next patron to be notified, or None if no holds
    """
    # Find the first PENDING hold (lowest position)
    result = await session.execute(
        select(HoldModel)
        .where(
            HoldModel.book_id == book_id,
            HoldModel.status == HoldStatus.PENDING.value,
        )
        .order_by(HoldModel.position)
        .limit(1)
    )
    next_hold = result.scalar_one_or_none()

    if not next_hold:
        # No pending holds
        return None

    # Update hold to READY status
    now = datetime.now(UTC)
    next_hold.status = HoldStatus.READY.value
    next_hold.notified_at = now
    next_hold.expires_at = now + timedelta(days=DEFAULT_HOLD_EXPIRY_DAYS)

    session.add(next_hold)
    # Note: commit will be done by the caller

    return next_hold.patron_id
