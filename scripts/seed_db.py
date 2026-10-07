#!/usr/bin/env python3
"""Seed the database with Hanno Memorial Library catalog data."""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "catalog" / "src"))
sys.path.insert(0, str(project_root / "shared" / "src"))

from sqlmodel import Session, select
from catalog.db import sync_engine, init_db
from catalog.models import (
    BookModel,
    BookInstanceModel,
    PatronModel,
    CheckoutModel,
    HoldModel,
    FineModel,
)
from shared.constants import InstanceStatus, ItemCondition


def load_json(filename: str) -> list[dict] | dict:
    """Load JSON data from the data directory."""
    data_dir = project_root / "data"
    with open(data_dir / filename) as f:
        return json.load(f)


def seed_books_from_hanno_catalog(session: Session) -> int:
    """Seed books from the Hanno Memorial Library catalog."""
    catalog = load_json("hanno_memorial_library_catalog.json")
    books_data = catalog.get("books", [])

    for book_data in books_data:
        book = BookModel(
            id=book_data["id"],
            title=book_data["title"],
            author=book_data["author"],
            isbn=book_data.get("isbn"),
            genres=book_data.get("genres", []),
            summary=book_data.get("summary"),
            publication_year=book_data.get("publication_year"),
            # Hanno-specific fields
            author_dates=book_data.get("author_dates"),
            stratum=book_data.get("stratum"),
            publisher=book_data.get("publisher"),
            page_count=book_data.get("page_count"),
            setting_era=book_data.get("setting_era"),
            series=book_data.get("series"),
            series_position=book_data.get("series_position"),
            shelf_location=book_data.get("shelf_location"),
            related_works=book_data.get("related_works", []),
            notes=book_data.get("notes"),
            in_library=book_data.get("in_library", True),
        )
        session.add(book)

    session.commit()
    return len(books_data)


def seed_books_from_childrens_batch(session: Session) -> int:
    """Seed children's books from batch file."""
    batch = load_json("batch_01_childrens_fables.json")
    books_data = batch.get("books", [])

    for book_data in books_data:
        book = BookModel(
            id=book_data["id"],
            title=book_data["title"],
            author=book_data["author"],
            isbn=book_data.get("isbn"),
            genres=book_data.get("genres", []),
            summary=book_data.get("summary"),
            publication_year=book_data.get("publication_year"),
            # Hanno-specific fields
            author_dates=book_data.get("author_dates"),
            stratum=book_data.get("stratum"),
            publisher=book_data.get("publisher"),
            page_count=book_data.get("page_count"),
            notes=book_data.get("notes"),
            in_library=True,  # Children's books available at HML
            # Children's book extensions
            age_range=book_data.get("age_range"),
            reading_level=book_data.get("reading_level"),
            illustrations=book_data.get("illustrations", False),
            illustrator=book_data.get("illustrator"),
        )
        session.add(book)

    session.commit()
    return len(books_data)


def generate_instances_for_books(session: Session) -> int:
    """Generate book instances for seeded books."""
    # Query all books
    books = session.exec(select(BookModel)).all()

    instance_count = 0
    conditions = [ItemCondition.EXCELLENT, ItemCondition.GOOD, ItemCondition.GOOD, ItemCondition.FAIR]
    statuses = [InstanceStatus.AVAILABLE, InstanceStatus.AVAILABLE, InstanceStatus.CHECKED_OUT]

    for book in books:
        # Create 1-3 instances per book
        num_instances = (hash(book.id) % 3) + 1

        for i in range(num_instances):
            instance_id = f"inst-{book.id.split('-')[1]}-{chr(97 + i)}"  # e.g., "inst-001-a"
            barcode = f"HAN-ITEM-{book.id.split('-')[1]}{chr(65 + i)}"  # e.g., "HAN-ITEM-001A"

            # Derive call number from shelf location or stratum
            call_number = None
            if book.shelf_location:
                call_number = book.shelf_location
            elif book.stratum:
                stratum_prefix = ["", "TRAG", "HIST", "MOD", "TECH", "CHLD", "POET", "PHIL", "TRANS"][book.stratum]
                author_part = book.author.split()[-1][:3].upper() if book.author else "UNK"
                call_number = f"{stratum_prefix} {author_part} {book.publication_year or ''}"

            # Vary status and condition
            status = statuses[(hash(instance_id) + i) % len(statuses)]
            condition = conditions[(hash(instance_id) + i) % len(conditions)]

            instance = BookInstanceModel(
                id=instance_id,
                book_id=book.id,
                barcode=barcode,
                call_number=call_number,
                status=status,
                location=book.shelf_location if status == InstanceStatus.AVAILABLE else None,
                condition=condition,
            )
            session.add(instance)
            instance_count += 1

    session.commit()
    return instance_count


def seed_patrons(session: Session) -> int:
    """Seed Hanno Memorial Library patrons."""
    patrons_data = load_json("hanno_patrons.json")

    for patron_data in patrons_data:
        patron = PatronModel(
            id=patron_data["id"],
            barcode=patron_data.get("barcode"),
            name=patron_data["name"],
            email=patron_data["email"],
            phone=patron_data.get("phone"),
            category=patron_data.get("category", "adult"),
            checkout_limit=patron_data.get("checkout_limit", 10),
            hold_limit=patron_data.get("hold_limit", 10),
        )
        session.add(patron)

    session.commit()
    return len(patrons_data)


def seed_checkouts(session: Session) -> int:
    """Create checkouts for instances that are checked out."""
    # Find all checked out instances
    instances = session.exec(
        select(BookInstanceModel).where(BookInstanceModel.status == InstanceStatus.CHECKED_OUT)
    ).all()

    patrons = session.exec(select(PatronModel)).all()
    if not patrons:
        return 0

    checkout_count = 0
    for i, inst in enumerate(instances):
        # Assign to patrons round-robin
        patron = patrons[i % len(patrons)]

        checkout = CheckoutModel(
            id=f"checkout-{inst.id}",
            instance_id=inst.id,
            patron_id=patron.id,
            checked_out_at=datetime.now(UTC) - timedelta(days=7),
            due_date=datetime.now(UTC) + timedelta(days=7),
            status="active",
        )
        session.add(checkout)
        checkout_count += 1

    session.commit()
    return checkout_count


def main():
    """Run the seed process for Hanno Memorial Library."""
    print("=" * 60)
    print("  Hanno Memorial Library - Database Seeding")
    print("  \"Long Memory\" - Elephants never forget")
    print("=" * 60)
    print()

    print("Initializing database...")
    init_db()

    print("\nSeeding catalog data from Hanno Memorial Library...")
    with Session(sync_engine) as session:
        # Seed books from main catalog
        book_count = seed_books_from_hanno_catalog(session)
        print(f"  ✓ Seeded {book_count} books from Hanno catalog (Strata I-IV)")

        # Seed children's books
        children_count = seed_books_from_childrens_batch(session)
        print(f"  ✓ Seeded {children_count} children's books (Stratum V)")

        # Generate instances
        instance_count = generate_instances_for_books(session)
        print(f"  ✓ Generated {instance_count} book instances")

        # Seed patrons
        patron_count = seed_patrons(session)
        print(f"  ✓ Seeded {patron_count} patrons")

        # Create checkouts
        checkout_count = seed_checkouts(session)
        print(f"  ✓ Created {checkout_count} checkout records")

    print()
    print("=" * 60)
    print(f"  Total: {book_count + children_count} books, {instance_count} instances")
    print("  ✓ Database seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
