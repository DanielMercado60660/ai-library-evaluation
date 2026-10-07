"""API routes for the catalog service."""

import json
import logging
import os
from datetime import datetime, timedelta, UTC
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, text, delete

from catalog.db import get_session
from catalog.models import BookModel, BookInstanceModel, PatronModel, CheckoutModel, HoldModel, FineModel
from shared.eval.admin_seed import eval_mode_enabled
from shared.constants import InstanceStatus

_logger = logging.getLogger(__name__)
from catalog.schemas import (
    BookSearchParams,
    BookSearchResponse,
    BookDetailResponse,
    BookAvailabilityResponse,
    InstanceStatusUpdate,
    HealthResponse,
    LibraryInfoResponse,
)
from shared.schemas import Book, BookInstance, BookWithAvailability, BookAvailability
from shared.constants import InstanceStatus

LIBRARY_CODE = os.getenv("LIBRARY_CODE", "hanno-memorial")
LIBRARY_NAME = os.getenv("LIBRARY_NAME", "Hanno Memorial Library")

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for the catalog service."""
    return HealthResponse(
        status="healthy",
        service="catalog",
        version="0.2.0",
        library=LIBRARY_NAME,
        library_code=LIBRARY_CODE,
    )


@router.get("/library/info", response_model=LibraryInfoResponse)
async def library_info(session: AsyncSession = Depends(get_session)):
    """Return library identity and book count."""
    count_result = await session.execute(select(func.count()).select_from(BookModel))
    book_count = count_result.scalar() or 0
    return LibraryInfoResponse(
        code=LIBRARY_CODE,
        name=LIBRARY_NAME,
        book_count=book_count,
    )


@router.get("/books", response_model=BookSearchResponse)
async def search_books(
    q: str | None = Query(None, description="Search query for title or author"),
    isbn: str | None = Query(None, description="Filter by exact ISBN"),
    genre: str | None = Query(None, description="Filter by genre"),
    author: str | None = Query(None, description="Filter by author name"),
    stratum: int | None = Query(None, ge=1, le=13, description="Filter by stratum (1-13)"),
    series: str | None = Query(None, description="Filter by series name"),
    available: bool | None = Query(None, description="Only show available books"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Search the Hanno Memorial Library catalog."""
    # Build base query
    query = select(BookModel)

    # Apply search filters
    if q:
        search_term = f"%{q}%"
        query = query.where(
            or_(
                BookModel.title.ilike(search_term),
                BookModel.author.ilike(search_term),
                BookModel.summary.ilike(search_term),
            )
        )

    if isbn:
        # Exact ISBN match
        query = query.where(BookModel.isbn == isbn)

    if genre:
        # SQLite JSON containment works reliably for scalar contains values.
        query = query.where(BookModel.genres.contains(genre))

    if author:
        query = query.where(BookModel.author.ilike(f"%{author}%"))

    if stratum:
        query = query.where(BookModel.stratum == stratum)

    if series:
        query = query.where(BookModel.series.ilike(f"%{series}%"))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await session.execute(query)
    books = result.scalars().all()

    # Get availability for each book
    books_with_availability = []
    for book in books:
        if genre and genre not in (book.genres or []):
            continue

        # Count instances
        instance_query = select(func.count()).where(
            BookInstanceModel.book_id == book.id
        )
        total_copies_result = await session.execute(instance_query)
        total_copies = total_copies_result.scalar() or 0

        # Count available instances
        available_query = select(func.count()).where(
            BookInstanceModel.book_id == book.id,
            BookInstanceModel.status == InstanceStatus.AVAILABLE,
        )
        available_result = await session.execute(available_query)
        available_copies = available_result.scalar() or 0

        # Skip if filtering for available and none available
        if available and available_copies == 0:
            continue

        books_with_availability.append(
            BookWithAvailability(
                id=book.id,
                title=book.title,
                author=book.author,
                isbn=book.isbn,
                genres=book.genres,
                summary=book.summary,
                publication_year=book.publication_year,
                # Hanno-specific fields
                author_dates=book.author_dates,
                stratum=book.stratum,
                publisher=book.publisher,
                page_count=book.page_count,
                setting_era=book.setting_era,
                series=book.series,
                series_position=book.series_position,
                shelf_location=book.shelf_location,
                related_works=book.related_works or [],
                notes=book.notes,
                # Children's extensions
                age_range=book.age_range,
                reading_level=book.reading_level,
                illustrations=book.illustrations or False,
                illustrator=book.illustrator,
                # Availability
                total_copies=total_copies,
                available_copies=available_copies,
            )
        )

    return BookSearchResponse(
        books=books_with_availability,
        total=total if not available else len(books_with_availability),
        limit=limit,
        offset=offset,
    )


@router.get("/books/{book_id}", response_model=BookDetailResponse)
async def get_book(
    book_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get details for a specific book."""
    # Get the book
    result = await session.execute(
        select(BookModel).where(BookModel.id == book_id)
    )
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # Get all instances
    instances_result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.book_id == book_id)
    )
    instances = instances_result.scalars().all()

    # Count availability
    total_copies = len(instances)
    available_copies = sum(
        1 for i in instances if i.status == InstanceStatus.AVAILABLE
    )

    return BookDetailResponse(
        book=Book(
            id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            genres=book.genres,
            summary=book.summary,
            publication_year=book.publication_year,
            # Hanno-specific fields
            author_dates=book.author_dates,
            stratum=book.stratum,
            publisher=book.publisher,
            page_count=book.page_count,
            setting_era=book.setting_era,
            series=book.series,
            series_position=book.series_position,
            shelf_location=book.shelf_location,
            related_works=book.related_works or [],
            notes=book.notes,
            # Children's extensions
            age_range=book.age_range,
            reading_level=book.reading_level,
            illustrations=book.illustrations or False,
            illustrator=book.illustrator,
        ),
        instances=[
            BookInstance(
                id=i.id,
                book_id=i.book_id,
                barcode=i.barcode,
                call_number=i.call_number,
                status=i.status,
                location=i.location,
                condition=i.condition,
                condition_notes=i.condition_notes,
            )
            for i in instances
        ],
        total_copies=total_copies,
        available_copies=available_copies,
    )


@router.get("/books/{book_id}/instances", response_model=list[BookInstance])
async def get_book_instances(
    book_id: str,
    status: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Get all instances of a specific book, optionally filtered by status."""
    # Verify book exists
    book_result = await session.execute(
        select(BookModel.id).where(BookModel.id == book_id)
    )
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    # Build query with optional status filter
    query = select(BookInstanceModel).where(BookInstanceModel.book_id == book_id)
    if status:
        query = query.where(BookInstanceModel.status == status)

    # Get instances
    result = await session.execute(query)
    instances = result.scalars().all()

    return [
        BookInstance(
            id=i.id,
            book_id=i.book_id,
            barcode=i.barcode,
            call_number=i.call_number,
            status=i.status,
            location=i.location,
            condition=i.condition,
            condition_notes=i.condition_notes,
        )
        for i in instances
    ]


@router.get("/books/{book_id}/availability", response_model=BookAvailabilityResponse)
async def get_book_availability(
    book_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get detailed availability summary for a book."""
    # Verify book exists
    book_result = await session.execute(
        select(BookModel.id).where(BookModel.id == book_id)
    )
    if not book_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Book not found")

    # Get all instances
    result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.book_id == book_id)
    )
    instances = result.scalars().all()

    # Count by status
    total_copies = len(instances)
    available = sum(1 for i in instances if i.status == InstanceStatus.AVAILABLE)
    checked_out = sum(1 for i in instances if i.status == InstanceStatus.CHECKED_OUT)
    on_hold_shelf = sum(1 for i in instances if i.status == InstanceStatus.HOLD_SHELF)
    in_processing = sum(1 for i in instances if i.status == InstanceStatus.PROCESSING)

    # Calculate earliest return date from active checkouts
    earliest_return_date = None
    if checked_out > 0:
        try:
            checked_out_ids = [i.id for i in instances if i.status == InstanceStatus.CHECKED_OUT]
            if checked_out_ids:
                placeholders = ", ".join(f":id_{j}" for j in range(len(checked_out_ids)))
                params = {f"id_{j}": iid for j, iid in enumerate(checked_out_ids)}
                erd_result = await session.execute(
                    text(
                        f"SELECT MIN(due_date) FROM checkouts "
                        f"WHERE instance_id IN ({placeholders}) "
                        f"AND status = 'active'"
                    ),
                    params,
                )
                row = erd_result.first()
                if row and row[0]:
                    val = row[0]
                    earliest_return_date = val if isinstance(val, datetime) else datetime.fromisoformat(str(val))
        except Exception:
            # Checkouts table may not exist in standalone catalog deployments
            pass

    return BookAvailabilityResponse(
        availability=BookAvailability(
            book_id=book_id,
            total_copies=total_copies,
            available=available,
            checked_out=checked_out,
            on_hold_shelf=on_hold_shelf,
            in_processing=in_processing,
            earliest_return_date=earliest_return_date,
        )
    )


@router.patch("/instances/{instance_id}/status", response_model=BookInstance)
async def update_instance_status(
    instance_id: str,
    update: InstanceStatusUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Update the status of a book instance."""
    # Get the instance
    result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
    )
    instance = result.scalar_one_or_none()

    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    # Validate status value
    valid_statuses = ["available", "checked_out", "hold_shelf", "processing", "missing", "damaged"]
    if update.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
        )

    # Update status
    instance.status = update.status
    await session.commit()
    await session.refresh(instance)

    return BookInstance(
        id=instance.id,
        book_id=instance.book_id,
        barcode=instance.barcode,
        call_number=instance.call_number,
        status=instance.status,
        location=instance.location,
        condition=instance.condition,
        condition_notes=instance.condition_notes,
    )


# --- Admin: Eval Reset & Seed ---

_DATA_DIR = Path(__file__).resolve().parents[4] / "data"


@router.post("/admin/reset-and-seed")
async def admin_reset_and_seed(session: AsyncSession = Depends(get_session)):
    """Drop all rows and re-seed from JSON data files.

    Gated behind EVAL_MODE=true environment variable.
    """
    if not eval_mode_enabled():
        raise HTTPException(status_code=403, detail="EVAL_MODE is not enabled")

    # Delete in dependency order
    for model in (FineModel, HoldModel, CheckoutModel, BookInstanceModel, PatronModel, BookModel):
        await session.execute(delete(model))
    await session.commit()

    records = 0

    # Seed books from catalog
    catalog_path = _DATA_DIR / "hanno_memorial_library_catalog.json"
    if catalog_path.exists():
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        for bd in catalog.get("books", []):
            session.add(BookModel(
                id=bd["id"], title=bd["title"], author=bd["author"],
                isbn=bd.get("isbn"), genres=bd.get("genres", []),
                summary=bd.get("summary"), publication_year=bd.get("publication_year"),
                author_dates=bd.get("author_dates"), stratum=bd.get("stratum"),
                publisher=bd.get("publisher"), page_count=bd.get("page_count"),
                setting_era=bd.get("setting_era"), series=bd.get("series"),
                series_position=bd.get("series_position"),
                shelf_location=bd.get("shelf_location"),
                related_works=bd.get("related_works", []),
                notes=bd.get("notes"), in_library=bd.get("in_library", True),
            ))
            records += 1
        await session.commit()

    # Seed children's fables
    children_path = _DATA_DIR / "batch_01_childrens_fables.json"
    if children_path.exists():
        batch = json.loads(children_path.read_text(encoding="utf-8"))
        for bd in batch.get("books", []):
            session.add(BookModel(
                id=bd["id"], title=bd["title"], author=bd["author"],
                isbn=bd.get("isbn"), genres=bd.get("genres", []),
                summary=bd.get("summary"), publication_year=bd.get("publication_year"),
                author_dates=bd.get("author_dates"), stratum=bd.get("stratum"),
                publisher=bd.get("publisher"), page_count=bd.get("page_count"),
                notes=bd.get("notes"), in_library=True,
                age_range=bd.get("age_range"), reading_level=bd.get("reading_level"),
                illustrations=bd.get("illustrations", False),
                illustrator=bd.get("illustrator"),
            ))
            records += 1
        await session.commit()

    # Generate instances (1-3 per book)
    books_result = await session.execute(select(BookModel))
    books = books_result.scalars().all()
    for book in books:
        num_inst = (hash(book.id) % 3) + 1
        for i in range(num_inst):
            num_part = book.id.split("-")[1]
            inst_id = f"inst-{num_part}-{chr(97 + i)}"
            barcode = f"HAN-ITEM-{num_part}{chr(65 + i)}"
            status = InstanceStatus.AVAILABLE if i < 2 else InstanceStatus.CHECKED_OUT
            session.add(BookInstanceModel(
                id=inst_id, book_id=book.id, barcode=barcode,
                call_number=book.shelf_location,
                status=status,
                location=book.shelf_location if status == InstanceStatus.AVAILABLE else None,
                condition="good",
            ))
            records += 1
        await session.commit()

    # Seed patrons
    patrons_path = _DATA_DIR / "hanno_patrons.json"
    if patrons_path.exists():
        patrons = json.loads(patrons_path.read_text(encoding="utf-8"))
        for pd in patrons:
            session.add(PatronModel(
                id=pd["id"], barcode=pd.get("barcode"), name=pd["name"],
                email=pd["email"], phone=pd.get("phone"),
                category=pd.get("category", "adult"),
                checkout_limit=pd.get("checkout_limit", 10),
                hold_limit=pd.get("hold_limit", 10),
            ))
            records += 1
        await session.commit()

    _logger.info("Catalog admin reset-and-seed completed: %d records", records)
    return {"status": "seeded", "service": "catalog", "records": records}
