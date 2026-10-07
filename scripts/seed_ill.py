#!/usr/bin/env python3
"""Seed the ILL service database.

This script seeds sample ILL requests and inbound loans for the ILL service.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "ill" / "src"))
sys.path.insert(0, str(project_root / "shared" / "src"))

from sqlmodel import Session
from ill.db import sync_engine, init_db
from ill.models import ILLRequestModel, InboundLoanModel


def seed_sample_ill_requests(session: Session) -> int:
    """Create sample outbound ILL requests (borrowing from other libraries)."""
    sample_requests = [
        {
            "id": "ill-req-001",
            "book_id": "ext-book-501",  # External library's book ID
            "book_title": "The Chronicles of Mammoth Valley",
            "isbn": "978-1-MAMMOTH-001",
            "author": "Dr. Valley Historian",
            "patron_id": "patron-001",
            "patron_reference": "HAN-P-001",
            "source_library": "mammoth-valley-library",
            "status": "received",
            "requested_days_ago": 15,
            "shipped_days_ago": 10,
            "received_days_ago": 7,
            "due_days_from_now": 21,
            "loan_period_days": 28,
        },
        {
            "id": "ill-req-002",
            "book_id": "ext-book-601",
            "book_title": "Mastodon Institute Proceedings Vol. 42",
            "isbn": "978-2-MASTODON-042",
            "author": "Various Authors",
            "patron_id": "patron-002",
            "patron_reference": "HAN-P-002",
            "source_library": "mastodon-institute-library",
            "status": "shipped",
            "requested_days_ago": 5,
            "shipped_days_ago": 2,
            "received_days_ago": None,
            "due_days_from_now": None,
            "loan_period_days": 28,
        },
        {
            "id": "ill-req-003",
            "book_id": "ext-book-701",
            "book_title": "Advanced Pachyderm Algorithms",
            "isbn": "978-3-TECH-101",
            "author": "Dr. T. Tusker",
            "patron_id": "patron-006",
            "patron_reference": "HAN-P-006",
            "source_library": "university-library",
            "status": "requested",
            "requested_days_ago": 2,
            "shipped_days_ago": None,
            "received_days_ago": None,
            "due_days_from_now": None,
            "loan_period_days": 28,
        },
    ]

    for req_data in sample_requests:
        request = ILLRequestModel(
            id=req_data["id"],
            book_id=req_data["book_id"],
            book_title=req_data["book_title"],
            isbn=req_data.get("isbn"),
            author=req_data.get("author"),
            patron_id=req_data["patron_id"],
            patron_reference=req_data["patron_reference"],
            source_library=req_data["source_library"],
            status=req_data["status"],
            requested_at=datetime.now(UTC) - timedelta(days=req_data["requested_days_ago"]),
            shipped_at=(
                datetime.now(UTC) - timedelta(days=req_data["shipped_days_ago"])
                if req_data["shipped_days_ago"]
                else None
            ),
            received_at=(
                datetime.now(UTC) - timedelta(days=req_data["received_days_ago"])
                if req_data["received_days_ago"]
                else None
            ),
            due_date=(
                datetime.now(UTC) + timedelta(days=req_data["due_days_from_now"])
                if req_data["due_days_from_now"]
                else None
            ),
            loan_period_days=req_data.get("loan_period_days"),
        )
        session.add(request)

    session.commit()
    return len(sample_requests)


def seed_sample_inbound_loans(session: Session) -> int:
    """Create sample inbound loans (lending to other libraries)."""
    sample_loans = [
        {
            "id": "inbound-001",
            "instance_id": "inst-015-a",  # One of our instances
            "book_id": "book-015",
            "requesting_library": "mastodon-institute-library",
            "patron_reference": "MAST-P-042",  # Their patron ID (opaque to us)
            "status": "active",
            "approved_days_ago": 20,
            "shipped_days_ago": 18,
            "due_days_from_now": 8,
            "loan_period_days": 28,
        },
        {
            "id": "inbound-002",
            "instance_id": "inst-020-b",
            "book_id": "book-020",
            "requesting_library": "mammoth-valley-library",
            "patron_reference": "MAM-P-015",
            "status": "shipped",
            "approved_days_ago": 3,
            "shipped_days_ago": 1,
            "due_days_from_now": 27,
            "loan_period_days": 28,
        },
    ]

    for loan_data in sample_loans:
        loan = InboundLoanModel(
            id=loan_data["id"],
            instance_id=loan_data["instance_id"],
            book_id=loan_data["book_id"],
            requesting_library=loan_data["requesting_library"],
            patron_reference=loan_data["patron_reference"],
            status=loan_data["status"],
            approved_at=datetime.now(UTC) - timedelta(days=loan_data["approved_days_ago"]),
            shipped_at=(
                datetime.now(UTC) - timedelta(days=loan_data["shipped_days_ago"])
                if loan_data.get("shipped_days_ago")
                else None
            ),
            due_date=datetime.now(UTC) + timedelta(days=loan_data["due_days_from_now"]),
            loan_period_days=loan_data["loan_period_days"],
        )
        session.add(loan)

    session.commit()
    return len(sample_loans)


def main():
    """Run the seed process for ILL service."""
    print("=" * 60)
    print("  ILL Service - Database Seeding")
    print("=" * 60)
    print()

    print("Initializing database...")
    init_db()

    print("\nSeeding ILL data...")
    with Session(sync_engine) as session:
        # Seed outbound ILL requests
        request_count = seed_sample_ill_requests(session)
        print(f"  ✓ Created {request_count} outbound ILL requests")

        # Seed inbound loans
        loan_count = seed_sample_inbound_loans(session)
        print(f"  ✓ Created {loan_count} inbound loan records")

    print()
    print("=" * 60)
    print("  ✓ ILL database seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
