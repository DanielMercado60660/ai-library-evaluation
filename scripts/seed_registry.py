#!/usr/bin/env python3
"""Seed the registry database with sample partner libraries."""

import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from registry.db import sync_engine
from registry.models import PartnerLibraryModel, LibraryMetricsModel
from sqlmodel import Session, SQLModel


def seed_partner_libraries(session: Session) -> int:
    """Create sample partner libraries with realistic metrics."""
    libraries_data = [
        {
            "library": {
                "code": "mastodon-institute",
                "name": "Mastodon Institute Library",
                "display_name": "The Mastodon Institute",
                "contact_name": "Dr. Tusk Paleontolus",
                "contact_email": "ill@mastodon-institute.edu",
                "contact_phone": "555-PALEO1",
                "address": "123 Fossil Lane, Mastodon City, MC 54321",
                "member_since": datetime.now(UTC) - timedelta(days=1825),  # 5 years
                "lending_enabled": True,
                "borrowing_enabled": True,
                "loan_period_days": 28,
                "auto_approve_requests": True,
                "specializations": ["paleontology", "ancient-history", "geology"],
                "notes": "Excellent academic partner with extensive paleontology collection.",
            },
            "metrics": {
                "total_requests_sent": 45,
                "total_requests_received": 52,
                "requests_approved": 48,
                "requests_denied": 4,
                "avg_response_time_hours": 18.5,
                "fulfillment_rate": 0.92,
                "on_time_return_rate": 0.95,
                "overdue_items_count": 1,
                "lost_items_count": 0,
                "last_request_sent": datetime.now(UTC) - timedelta(days=3),
                "last_request_received": datetime.now(UTC) - timedelta(days=5),
            }
        },
        {
            "library": {
                "code": "mammoth-valley",
                "name": "Mammoth Valley Public Library",
                "display_name": "Mammoth Valley Library",
                "contact_name": "Ms. Ivory Booksworth",
                "contact_email": "interlibrary@mammothvalley.org",
                "contact_phone": "555-MVLIB1",
                "address": "456 Valley Road, Mammoth Valley, MV 67890",
                "member_since": datetime.now(UTC) - timedelta(days=2555),  # 7 years
                "lending_enabled": True,
                "borrowing_enabled": True,
                "loan_period_days": 28,
                "auto_approve_requests": False,  # Requires manual approval
                "specializations": ["local-history", "genealogy", "fiction"],
                "notes": "Reliable public library with strong local history collection.",
            },
            "metrics": {
                "total_requests_sent": 67,
                "total_requests_received": 38,
                "requests_approved": 35,
                "requests_denied": 3,
                "avg_response_time_hours": 36.0,
                "fulfillment_rate": 0.92,
                "on_time_return_rate": 0.88,
                "overdue_items_count": 3,
                "lost_items_count": 1,
                "last_request_sent": datetime.now(UTC) - timedelta(days=7),
                "last_request_received": datetime.now(UTC) - timedelta(days=12),
            }
        },
        {
            "library": {
                "code": "ivory-university",
                "name": "Ivory University Research Library",
                "display_name": "Ivory University",
                "contact_name": "Prof. Trunsworth Scholar",
                "contact_email": "research-ill@ivory.edu",
                "contact_phone": "555-IVORY9",
                "address": "789 Academic Drive, Ivory City, IC 13579",
                "member_since": datetime.now(UTC) - timedelta(days=3650),  # 10 years
                "lending_enabled": True,
                "borrowing_enabled": True,
                "loan_period_days": 28,
                "auto_approve_requests": False,
                "specializations": ["science", "technology", "mathematics", "philosophy"],
                "notes": "Large research library with comprehensive STEM collection.",
            },
            "metrics": {
                "total_requests_sent": 123,
                "total_requests_received": 98,
                "requests_approved": 85,
                "requests_denied": 13,
                "avg_response_time_hours": 24.0,
                "fulfillment_rate": 0.87,
                "on_time_return_rate": 0.96,
                "overdue_items_count": 2,
                "lost_items_count": 0,
                "last_request_sent": datetime.now(UTC) - timedelta(days=2),
                "last_request_received": datetime.now(UTC) - timedelta(days=4),
            }
        },
        {
            "library": {
                "code": "tusk-conservatory",
                "name": "Tusk Conservatory Archives",
                "display_name": "The Tusk Conservatory",
                "contact_name": "Curator Pachydon Archivist",
                "contact_email": "archives@tusk-conservatory.org",
                "contact_phone": "555-MUSIC7",
                "address": "321 Melody Lane, Tusk Town, TT 24680",
                "member_since": datetime.now(UTC) - timedelta(days=730),  # 2 years
                "lending_enabled": True,
                "borrowing_enabled": True,
                "loan_period_days": 21,  # Shorter loan period for rare items
                "auto_approve_requests": False,
                "specializations": ["music", "performing-arts", "rare-manuscripts"],
                "notes": "Specialized collection of rare musical manuscripts. Careful handling required.",
            },
            "metrics": {
                "total_requests_sent": 12,
                "total_requests_received": 15,
                "requests_approved": 12,
                "requests_denied": 3,
                "avg_response_time_hours": 48.0,
                "fulfillment_rate": 0.80,
                "on_time_return_rate": 1.0,
                "overdue_items_count": 0,
                "lost_items_count": 0,
                "last_request_sent": datetime.now(UTC) - timedelta(days=21),
                "last_request_received": datetime.now(UTC) - timedelta(days=18),
            }
        },
    ]

    count = 0
    for lib_data in libraries_data:
        # Create library
        library = PartnerLibraryModel(**lib_data["library"])
        session.add(library)

        # Create metrics
        metrics_data = lib_data["metrics"]
        metrics = LibraryMetricsModel(
            library_code=library.code,
            last_updated=datetime.now(UTC),
            **metrics_data
        )
        session.add(metrics)

        count += 1

    return count


def main():
    """Main seeding function."""
    print("=" * 60)
    print("  Registry Service - Database Seeding")
    print("=" * 60)

    # Initialize database
    print("\nInitializing database...")
    SQLModel.metadata.create_all(sync_engine)

    # Seed data
    with Session(sync_engine) as session:
        print("\nSeeding partner libraries...")

        # Check if already seeded
        from sqlmodel import select
        existing_count = len(session.exec(select(PartnerLibraryModel)).all())
        if existing_count > 0:
            print(f"  ⚠  Database already contains {existing_count} libraries")
            print("  Skipping seed to avoid duplicates")
            print("\n" + "=" * 60)
            print("  ℹ  Registry database already seeded")
            print("=" * 60)
            return

        # Seed libraries
        count = seed_partner_libraries(session)
        session.commit()

        print(f"  ✓ Seeded {count} partner libraries with metrics")

    print("\n" + "=" * 60)
    print("  ✓ Registry database seeded successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
