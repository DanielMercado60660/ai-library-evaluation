"""MCP Server for Catalog Service.

This MCP server exposes book and instance resources/tools for AI agents.
It runs alongside the FastAPI HTTP server and provides direct database access
via the Model Context Protocol.
"""

import logging
import json
from datetime import datetime, UTC
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from catalog.db import async_engine
from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus

# Configure logging to stderr (not stdout, which would corrupt MCP messages)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("catalog-mcp-server")


# =============================================================================
# Resources - Read-only data access
# =============================================================================

@mcp.resource("book://{book_id}")
async def get_book(book_id: str) -> str:
    """Get detailed information about a book.

    Includes metadata, instances, and availability.
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(select(BookModel).where(BookModel.id == book_id))
        book = result.scalar_one_or_none()

        if not book:
            return json.dumps({"error": f"Book {book_id} not found"})

        instance_result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.book_id == book.id)
        )
        instances = instance_result.scalars().all()
        available_count = sum(1 for i in instances if i.status == InstanceStatus.AVAILABLE)

        return json.dumps({
            "id": book.id,
            "title": book.title,
            "author": book.author,
            "author_dates": book.author_dates,
            "isbn": book.isbn,
            "genres": book.genres,
            "summary": book.summary,
            "publication_year": book.publication_year,
            "stratum": book.stratum,
            "publisher": book.publisher,
            "page_count": book.page_count,
            "setting_era": book.setting_era,
            "series": book.series,
            "series_position": book.series_position,
            "shelf_location": book.shelf_location,
            "related_works": book.related_works,
            "notes": book.notes,
            "in_library": book.in_library,
            "age_range": book.age_range,
            "reading_level": book.reading_level,
            "illustrations": book.illustrations,
            "illustrator": book.illustrator,
            "total_copies": len(instances),
            "available_copies": available_count,
        }, indent=2)


@mcp.resource("instance://{instance_id}")
async def get_instance(instance_id: str) -> str:
    """Get detailed information about a book instance."""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
        )
        instance = result.scalar_one_or_none()

        if not instance:
            return json.dumps({"error": f"Instance {instance_id} not found"})

        return json.dumps({
            "id": instance.id,
            "book_id": instance.book_id,
            "barcode": instance.barcode,
            "call_number": instance.call_number,
            "status": instance.status.value if hasattr(instance.status, 'value') else str(instance.status),
            "location": instance.location,
            "condition": instance.condition.value if hasattr(instance.condition, 'value') else str(instance.condition),
            "condition_notes": instance.condition_notes,
            "created_at": instance.created_at.isoformat() if instance.created_at else None,
        }, indent=2)


@mcp.resource("search://books")
async def search_books_resource() -> str:
    """Get all books in the catalog (use the search_books tool for filtered searches)."""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(select(BookModel).limit(50))
        books = result.scalars().all()
        book_ids = [book.id for book in books]
        counts: dict[str, dict[str, int]] = {}
        if book_ids:
            count_result = await session.execute(
                select(
                    BookInstanceModel.book_id,
                    BookInstanceModel.status,
                    func.count(BookInstanceModel.id),
                )
                .where(BookInstanceModel.book_id.in_(book_ids))
                .group_by(BookInstanceModel.book_id, BookInstanceModel.status)
            )
            for book_id, status, count in count_result:
                key = status.value if hasattr(status, "value") else str(status)
                counts.setdefault(book_id, {})[key] = count

        book_list = []
        for book in books:
            book_counts = counts.get(book.id, {})
            available_count = book_counts.get(InstanceStatus.AVAILABLE.value, 0)
            total_copies = sum(book_counts.values())
            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "stratum": book.stratum,
                "total_copies": total_copies,
                "available_copies": available_count,
            })

        return json.dumps({
            "total": len(book_list),
            "books": book_list
        }, indent=2)


@mcp.resource("catalog://availability")
async def get_catalog_availability() -> str:
    """Get overall catalog availability statistics."""
    async with AsyncSession(async_engine) as session:
        # Total books
        total_books = await session.execute(select(func.count(BookModel.id)))
        book_count = total_books.scalar() or 0

        # Total instances
        total_instances = await session.execute(select(func.count(BookInstanceModel.id)))
        instance_count = total_instances.scalar() or 0

        # Available instances
        available = await session.execute(
            select(func.count(BookInstanceModel.id))
            .where(BookInstanceModel.status == InstanceStatus.AVAILABLE)
        )
        available_count = available.scalar() or 0

        # Checked out
        checked_out = await session.execute(
            select(func.count(BookInstanceModel.id))
            .where(BookInstanceModel.status == InstanceStatus.CHECKED_OUT)
        )
        checked_out_count = checked_out.scalar() or 0

        # On hold
        on_hold = await session.execute(
            select(func.count(BookInstanceModel.id))
            .where(BookInstanceModel.status == InstanceStatus.HOLD_SHELF)
        )
        on_hold_count = on_hold.scalar() or 0

        return json.dumps({
            "total_books": book_count,
            "total_instances": instance_count,
            "available": available_count,
            "checked_out": checked_out_count,
            "on_hold": on_hold_count,
            "availability_rate": round(available_count / instance_count * 100, 1) if instance_count > 0 else 0,
        }, indent=2)


# =============================================================================
# Tools - Actions that query or modify state
# =============================================================================

@mcp.tool()
async def search_books(
    query: str = "",
    author: str = "",
    genre: str = "",
    stratum: int | None = None,
    isbn: str = "",
    available_only: bool = False,
    limit: int = 20
) -> str:
    """Search the library catalog for books.

    Args:
        query: Search term to match against title or summary
        author: Filter by author name
        genre: Filter by genre
        stratum: Filter by catalog stratum (1-13)
        isbn: Search by ISBN
        available_only: Only return books with available copies
        limit: Maximum number of results

    Returns:
        JSON with matching books and availability info
    """
    async with AsyncSession(async_engine) as session:
        stmt = select(BookModel)

        # Apply filters
        if query:
            stmt = stmt.where(
                or_(
                    BookModel.title.ilike(f"%{query}%"),
                    BookModel.summary.ilike(f"%{query}%")
                )
            )
        if author:
            stmt = stmt.where(BookModel.author.ilike(f"%{author}%"))
        if genre:
            # Genre is stored as JSON list
            stmt = stmt.where(BookModel.genres.contains(genre))
        if stratum:
            stmt = stmt.where(BookModel.stratum == stratum)
        if isbn:
            stmt = stmt.where(BookModel.isbn == isbn)

        stmt = stmt.limit(limit)

        result = await session.execute(stmt)
        books = result.scalars().all()
        book_ids = [book.id for book in books]
        counts: dict[str, dict[str, int]] = {}
        if book_ids:
            count_result = await session.execute(
                select(
                    BookInstanceModel.book_id,
                    BookInstanceModel.status,
                    func.count(BookInstanceModel.id),
                )
                .where(BookInstanceModel.book_id.in_(book_ids))
                .group_by(BookInstanceModel.book_id, BookInstanceModel.status)
            )
            for book_id, status, count in count_result:
                key = status.value if hasattr(status, "value") else str(status)
                counts.setdefault(book_id, {})[key] = count

        # Filter by availability if requested
        book_list = []
        for book in books:
            book_counts = counts.get(book.id, {})
            available_count = book_counts.get(InstanceStatus.AVAILABLE.value, 0)
            total_copies = sum(book_counts.values())

            if available_only and available_count == 0:
                continue

            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "isbn": book.isbn,
                "stratum": book.stratum,
                "series": book.series,
                "total_copies": total_copies,
                "available_copies": available_count,
                "summary": book.summary[:200] + "..." if book.summary and len(book.summary) > 200 else book.summary,
            })

        return json.dumps({
            "query": query,
            "total": len(book_list),
            "books": book_list
        }, indent=2)


@mcp.tool()
async def check_availability(book_id: str) -> str:
    """Check availability of a specific book.

    Args:
        book_id: The ID of the book to check

    Returns:
        JSON with availability details for all instances
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(BookModel)
            .options(selectinload(BookModel.instances))
            .where(BookModel.id == book_id)
        )
        book = result.scalar_one_or_none()

        if not book:
            return json.dumps({"error": f"Book {book_id} not found"})

        instances = []
        for inst in book.instances:
            instances.append({
                "instance_id": inst.id,
                "barcode": inst.barcode,
                "status": inst.status.value if hasattr(inst.status, 'value') else str(inst.status),
                "location": inst.location,
                "condition": inst.condition.value if hasattr(inst.condition, 'value') else str(inst.condition),
            })

        available_count = sum(1 for i in instances if i["status"] == "available")

        return json.dumps({
            "book_id": book_id,
            "title": book.title,
            "total_copies": len(instances),
            "available_copies": available_count,
            "is_available": available_count > 0,
            "instances": instances
        }, indent=2)


@mcp.tool()
async def reserve_instance(
    instance_id: str,
    reason: str = "ILL loan"
) -> str:
    """Reserve a book instance for ILL or special use.

    Changes instance status to reflect it's reserved.

    Args:
        instance_id: The ID of the instance to reserve
        reason: The reason for reservation

    Returns:
        JSON with the updated instance status
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
        )
        instance = result.scalar_one_or_none()

        if not instance:
            return json.dumps({"error": f"Instance {instance_id} not found"})

        if instance.status != InstanceStatus.AVAILABLE:
            return json.dumps({
                "error": f"Instance is not available (current status: {instance.status.value if hasattr(instance.status, 'value') else str(instance.status)})"
            })

        # Reserve the instance
        instance.status = InstanceStatus.HOLD_SHELF

        await session.commit()
        await session.refresh(instance)

        return json.dumps({
            "success": True,
            "instance_id": instance.id,
            "new_status": instance.status.value if hasattr(instance.status, 'value') else str(instance.status),
            "reason": reason
        }, indent=2)


@mcp.tool()
async def release_instance(
    instance_id: str,
    reason: str = "Reservation released"
) -> str:
    """Release a reserved book instance back to available.

    Args:
        instance_id: The ID of the instance to release
        reason: The reason for release

    Returns:
        JSON with the updated instance status
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
        )
        instance = result.scalar_one_or_none()

        if not instance:
            return json.dumps({"error": f"Instance {instance_id} not found"})

        # Release the instance
        instance.status = InstanceStatus.AVAILABLE

        await session.commit()
        await session.refresh(instance)

        return json.dumps({
            "success": True,
            "instance_id": instance.id,
            "new_status": instance.status.value if hasattr(instance.status, 'value') else str(instance.status),
            "reason": reason
        }, indent=2)


@mcp.tool()
async def get_books_by_stratum(stratum: int) -> str:
    """Get all books in a specific catalog stratum.

    Strata:
    1 = Noble Tragedies
    2 = Histories & Memoirs
    3 = Modern Literary Works
    4 = Technical & Reference
    5 = Children's Tales
    6 = Poetry Collections
    7 = Philosophy & Treatises
    8 = Translated Works
    9 = Extended Tragedies
    10 = Extended Histories
    11 = Extended Modern Literary
    12 = Extended Technical
    13 = Genre Fiction

    Args:
        stratum: The stratum number (1-13)

    Returns:
        JSON with books in that stratum
    """
    if stratum < 1 or stratum > 13:
        return json.dumps({"error": f"Invalid stratum {stratum}. Must be 1-13."})

    stratum_names = {
        1: "Noble Tragedies",
        2: "Histories & Memoirs",
        3: "Modern Literary Works",
        4: "Technical & Reference",
        5: "Children's Tales",
        6: "Poetry Collections",
        7: "Philosophy & Treatises",
        8: "Translated Works",
        9: "Extended Tragedies",
        10: "Extended Histories",
        11: "Extended Modern Literary",
        12: "Extended Technical",
        13: "Genre Fiction",
    }

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(BookModel)
            .options(selectinload(BookModel.instances))
            .where(BookModel.stratum == stratum)
        )
        books = result.scalars().all()

        book_list = []
        for book in books:
            available_count = sum(1 for i in book.instances if i.status == InstanceStatus.AVAILABLE)
            book_list.append({
                "id": book.id,
                "title": book.title,
                "author": book.author,
                "total_copies": len(book.instances),
                "available_copies": available_count,
            })

        return json.dumps({
            "stratum": stratum,
            "stratum_name": stratum_names.get(stratum, "Unknown"),
            "total_books": len(book_list),
            "books": book_list
        }, indent=2)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
