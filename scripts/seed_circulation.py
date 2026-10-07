#!/usr/bin/env python3
"""Seed the circulation service database.

This script seeds patron and checkout data for the circulation service.
It assumes books and instances have been seeded in the catalog service.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC
from decimal import Decimal

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "services" / "circulation" / "src"))
sys.path.insert(0, str(project_root / "shared" / "src"))

from sqlmodel import Session, select
from circulation.db import sync_engine, init_db
from circulation.models import (
    PatronModel,
    CheckoutModel,
    HoldModel,
    FineModel,
)
from shared.constants import CheckoutStatus, HoldStatus, FineReason


def load_json(filename: str) -> list[dict] | dict:
    """Load JSON data from the data directory."""
    data_dir = project_root / "data"
    with open(data_dir / filename) as f:
        return json.load(f)


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
            blocked=patron_data.get("blocked", False),
            block_reason=patron_data.get("block_reason"),
        )
        session.add(patron)

    session.commit()
    return len(patrons_data)


def seed_sample_checkouts(session: Session) -> int:
    """Create some sample checkouts for testing."""
    # Get patrons
    patrons = session.exec(select(PatronModel)).all()
    if not patrons:
        return 0

    # Create sample checkouts (using instance IDs we know exist from catalog seed)
    sample_checkouts = [
        {
            "id": "checkout-001",
            "instance_id": "inst-001-a",
            "patron_id": "patron-001",
            "days_ago": 5,
            "due_days": 9,
        },
        {
            "id": "checkout-002",
            "instance_id": "inst-002-a",
            "patron_id": "patron-002",
            "days_ago": 10,
            "due_days": 4,
        },
        {
            "id": "checkout-003",
            "instance_id": "inst-003-a",
            "patron_id": "patron-003",
            "days_ago": 3,
            "due_days": 11,
        },
    ]

    for checkout_data in sample_checkouts:
        checkout = CheckoutModel(
            id=checkout_data["id"],
            instance_id=checkout_data["instance_id"],
            patron_id=checkout_data["patron_id"],
            checked_out_at=datetime.now(UTC) - timedelta(days=checkout_data["days_ago"]),
            due_date=datetime.now(UTC) + timedelta(days=checkout_data["due_days"]),
            status="active",
            renewals_used=0,
            max_renewals=2,
        )
        session.add(checkout)

    session.commit()
    return len(sample_checkouts)


def seed_sample_holds(session: Session) -> int:
    """Create some sample holds for testing."""
    # Get patrons
    patrons = session.exec(select(PatronModel)).all()
    if not patrons:
        return 0

    # Create sample holds (using book IDs we know exist from catalog seed)
    sample_holds = [
        {
            "id": "hold-001",
            "book_id": "book-005",
            "patron_id": "patron-004",
            "position": 1,
            "status": "pending",
        },
        {
            "id": "hold-002",
            "book_id": "book-010",
            "patron_id": "patron-005",
            "position": 1,
            "status": "ready",
            "notified_days_ago": 1,
        },
        {
            "id": "hold-003",
            "book_id": "book-005",
            "patron_id": "patron-006",
            "position": 2,
            "status": "pending",
        },
    ]

    for hold_data in sample_holds:
        hold = HoldModel(
            id=hold_data["id"],
            book_id=hold_data["book_id"],
            patron_id=hold_data["patron_id"],
            position=hold_data["position"],
            status=hold_data["status"],
            created_at=datetime.now(UTC) - timedelta(days=7),
            notified_at=(
                datetime.now(UTC) - timedelta(days=hold_data.get("notified_days_ago", 0))
                if "notified_days_ago" in hold_data
                else None
            ),
            expires_at=(
                datetime.now(UTC) + timedelta(days=3)
                if hold_data["status"] == "ready"
                else None
            ),
        )
        session.add(hold)

    session.commit()
    return len(sample_holds)


def seed_sample_fines(session: Session) -> int:
    """Create some sample fines for testing."""
    # Get patrons and checkouts
    patrons = session.exec(select(PatronModel)).all()
    checkouts = session.exec(select(CheckoutModel)).all()

    if not patrons:
        return 0

    # Create sample fines
    sample_fines = [
        {
            "id": "fine-001",
            "patron_id": "patron-002",
            "checkout_id": "checkout-002",
            "reason": "overdue",
            "amount": Decimal("2.50"),
            "description": "Overdue fine: $0.50/day x 5 days",
            "paid": False,
        },
        {
            "id": "fine-002",
            "patron_id": "patron-007",
            "checkout_id": None,
            "reason": "lost",
            "amount": Decimal("35.00"),
            "description": "Lost book replacement fee",
            "paid": True,
            "paid_days_ago": 3,
        },
    ]

    for fine_data in sample_fines:
        fine = FineModel(
            id=fine_data["id"],
            patron_id=fine_data["patron_id"],
            checkout_id=fine_data.get("checkout_id"),
            reason=fine_data["reason"],
            amount=float(fine_data["amount"]),
            description=fine_data.get("description"),
            paid=fine_data["paid"],
            paid_at=(
                datetime.now(UTC) - timedelta(days=fine_data.get("paid_days_ago", 0))
                if fine_data["paid"]
                else None
            ),
            created_at=datetime.now(UTC) - timedelta(days=10),
        )
        session.add(fine)

    session.commit()
    return len(sample_fines)


def main():
    """Run the seed process for circulation service."""
    print("=" * 60)
    print("  Circulation Service - Database Seeding")
    print("=" * 60)
    print()

    print("Initializing database...")
    init_db()

    print("\nSeeding circulation data...")
    with Session(sync_engine) as session:
        # Seed patrons
        patron_count = seed_patrons(session)
        print(f"  ✓ Seeded {patron_count} patrons")

        # Create sample checkouts
        checkout_count = seed_sample_checkouts(session)
        print(f"  ✓ Created {checkout_count} checkout records")

        # Create sample holds
        hold_count = seed_sample_holds(session)
        print(f"  ✓ Created {hold_count} hold records")

        # Create sample fines
        fine_count = seed_sample_fines(session)
        print(f"  ✓ Created {fine_count} fine records")

    print()
    print("=" * 60)
    print("  ✓ Circulation database seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
