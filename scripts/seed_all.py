#!/usr/bin/env python3
"""Master script to seed all service databases.

This orchestrates seeding across all three services in the correct order:
1. Catalog service (books, instances)
2. Circulation service (patrons, checkouts, holds, fines)
3. ILL service (ILL requests, inbound loans)
"""

import subprocess
import sys
import argparse
from pathlib import Path


def run_seed_script(script_name: str) -> bool:
    """Run a seed script and return success status."""
    script_path = Path(__file__).parent / script_name

    print(f"\n{'='*60}")
    print(f"Running {script_name}...")
    print(f"{'='*60}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            capture_output=False,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Error running {script_name}: {e}")
        return False


def main():
    """Run all seed scripts in order."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Seed all service databases")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    parser.add_argument(
        "--federated", action="store_true",
        help="Run federated network seed (seed_network.py) instead of single-library seed",
    )
    args = parser.parse_args()

    if args.federated:
        print("Running federated network seed...")
        if not run_seed_script("seed_network.py"):
            print("\n  Federated seed failed.")
            sys.exit(1)
        print("\nFederated seed complete.")
        return

    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "HANNO MEMORIAL LIBRARY SYSTEM" + " " * 18 + "║")
    print("║" + " " * 15 + "Database Seeding Suite" + " " * 21 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    print("This will seed all three service databases:")
    print("  1. Catalog Service (books, instances)")
    print("  2. Circulation Service (patrons, checkouts, holds, fines)")
    print("  3. ILL Service (requests, inbound loans)")
    print()

    # Ask for confirmation unless --yes flag is provided
    if not args.yes:
        try:
            response = input("Continue? [Y/n]: ").strip().lower()
            if response and response != 'y':
                print("Aborted.")
                return
        except EOFError:
            print("Non-interactive mode detected. Use --yes flag to proceed automatically.")
            return

    # Track success
    all_success = True

    # 1. Seed catalog (books and instances)
    if not run_seed_script("seed_db.py"):
        all_success = False
        print("\n⚠️  Catalog seeding failed. Continuing anyway...")

    # 2. Seed circulation (patrons, checkouts, holds, fines)
    if not run_seed_script("seed_circulation.py"):
        all_success = False
        print("\n⚠️  Circulation seeding failed. Continuing anyway...")

    # 3. Seed ILL (requests, inbound loans)
    if not run_seed_script("seed_ill.py"):
        all_success = False
        print("\n⚠️  ILL seeding failed. Continuing anyway...")

    # Final summary
    print("\n\n")
    print("╔" + "═" * 58 + "╗")
    if all_success:
        print("║" + " " * 18 + "✅ ALL SEEDS COMPLETE" + " " * 18 + "║")
    else:
        print("║" + " " * 10 + "⚠️  SEEDING COMPLETED WITH ERRORS" + " " * 12 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    if all_success:
        print("All service databases have been seeded successfully!")
        print()
        print("Next steps:")
        print("  • Start all services: docker-compose up")
        print("  • Or run individually for development")
        print()
    else:
        print("Some seeding operations failed. Check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
