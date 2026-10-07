#!/usr/bin/env python3
"""Seed a single library's catalog database from the network seed manifest.

Usage:
    python scripts/seed_spoke_catalog.py --library-code mastodon-institute
    python scripts/seed_spoke_catalog.py --library-code mastodon-institute --db-url sqlite:///./artifacts/federated-dbs/mastodon.db
    python scripts/seed_spoke_catalog.py --library-code hanno-memorial  # delegates to hub sources
"""

import argparse
import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "catalog" / "src"))
sys.path.insert(0, str(project_root / "shared" / "src"))

from sqlmodel import Session, create_engine, SQLModel, select
from catalog.models import BookModel, BookInstanceModel
from shared.constants import InstanceStatus, ItemCondition

DATA_DIR = project_root / "data"
MANIFEST_PATH = DATA_DIR / "network_seed_manifest.json"


def load_manifest() -> dict:
    """Load the network seed manifest."""
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def find_library_entry(manifest: dict, library_code: str) -> dict | None:
    """Find the hub or spoke entry for a given library code."""
    if manifest["hub"]["code"] == library_code:
        return manifest["hub"]
    for spoke in manifest.get("spokes", []):
        if spoke["code"] == library_code:
            return spoke
    return None


def load_books_from_source(source: dict) -> list[dict]:
    """Load books from a single source file entry."""
    filepath = DATA_DIR / source["file"]
    with open(filepath) as f:
        data = json.load(f)
    key = source.get("key", "books")
    return data.get(key, [])


def create_book_model(book_data: dict) -> BookModel:
    """Create a BookModel from raw book data."""
    return BookModel(
        id=book_data["id"],
        title=book_data["title"],
        author=book_data["author"],
        isbn=book_data.get("isbn"),
        genres=book_data.get("genres", []),
        summary=book_data.get("summary"),
        publication_year=book_data.get("publication_year"),
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
        age_range=book_data.get("age_range"),
        reading_level=book_data.get("reading_level"),
        illustrations=book_data.get("illustrations", False),
        illustrator=book_data.get("illustrator"),
    )


def generate_instances(session: Session, library_code: str) -> int:
    """Generate book instances for all books in the database."""
    books = session.exec(select(BookModel)).all()

    # Library-specific barcode prefix
    prefix_map = {
        "hanno-memorial": "HAN",
        "mastodon-institute": "MAS",
        "mammoth-valley": "MAM",
        "ivory-university": "IVY",
        "tusk-conservatory": "TUS",
    }
    prefix = prefix_map.get(library_code, library_code[:3].upper())

    conditions = [ItemCondition.EXCELLENT, ItemCondition.GOOD, ItemCondition.GOOD, ItemCondition.FAIR]
    statuses = [InstanceStatus.AVAILABLE, InstanceStatus.AVAILABLE, InstanceStatus.CHECKED_OUT]

    instance_count = 0
    for book in books:
        num_instances = (hash(book.id) % 3) + 1
        book_num = book.id.split("-")[1] if "-" in book.id else book.id

        for i in range(num_instances):
            instance_id = f"inst-{library_code}-{book_num}-{chr(97 + i)}"
            barcode = f"{prefix}-ITEM-{book_num}{chr(65 + i)}"

            call_number = None
            if book.shelf_location:
                call_number = book.shelf_location
            elif book.stratum:
                stratum_prefixes = ["", "TRAG", "HIST", "MOD", "TECH", "CHLD", "POET", "PHIL", "TRANS", "GENRE", "EXTH"]
                sp = stratum_prefixes[book.stratum] if book.stratum < len(stratum_prefixes) else f"S{book.stratum}"
                author_part = book.author.split()[-1][:3].upper() if book.author else "UNK"
                call_number = f"{sp} {author_part} {book.publication_year or ''}"

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


def seed_library(library_code: str, db_url: str | None = None) -> dict:
    """Seed a library's catalog database. Returns summary dict."""
    manifest = load_manifest()
    entry = find_library_entry(manifest, library_code)
    if entry is None:
        raise ValueError(f"Library '{library_code}' not found in manifest")

    if db_url is None:
        db_dir = project_root / "artifacts" / "federated-dbs"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{db_dir / library_code}.db"

    engine = create_engine(
        db_url,
        echo=False,
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
    )
    SQLModel.metadata.create_all(engine)

    book_count = 0
    with Session(engine) as session:
        for source in entry["sources"]:
            books = load_books_from_source(source)
            for book_data in books:
                session.add(create_book_model(book_data))
            book_count += len(books)
            session.commit()

        instance_count = generate_instances(session, library_code)

    return {
        "library_code": library_code,
        "library_name": entry["name"],
        "db_url": db_url,
        "books_seeded": book_count,
        "instances_generated": instance_count,
        "sources": [s["file"] for s in entry["sources"]],
    }


def main():
    parser = argparse.ArgumentParser(description="Seed a single library catalog from the network manifest.")
    parser.add_argument("--library-code", required=True, help="Library code (e.g. mastodon-institute)")
    parser.add_argument("--db-url", default=None, help="SQLAlchemy DB URL (default: sqlite under artifacts/federated-dbs/)")
    args = parser.parse_args()

    result = seed_library(args.library_code, args.db_url)

    print(f"  Library:   {result['library_name']} ({result['library_code']})")
    print(f"  DB:        {result['db_url']}")
    print(f"  Books:     {result['books_seeded']}")
    print(f"  Instances: {result['instances_generated']}")
    print(f"  Sources:   {', '.join(result['sources'])}")


if __name__ == "__main__":
    main()
