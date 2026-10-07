#!/usr/bin/env python3
"""Test the complete checkout workflow across services.

This script traces a patron searching for a book, finding it in the catalog,
and checking it out through the circulation service.
"""

import asyncio
import httpx
from datetime import datetime


CATALOG_URL = "http://localhost:8001"
CIRCULATION_URL = "http://localhost:8002"
ILL_URL = "http://localhost:8003"


def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_step(step_num: int, text: str):
    """Print a formatted step."""
    print(f"\n[Step {step_num}] {text}")


def print_response(data: dict, indent: int = 2):
    """Print formatted JSON response."""
    import json
    print(json.dumps(data, indent=indent, default=str))


async def test_complete_checkout_workflow():
    """Test: Patron searches catalog, finds book, checks it out."""
    print_header("COMPLETE CHECKOUT WORKFLOW TEST")
    print("\nScenario: Trunsworth Greyvale wants to check out a book")
    print("Patron: patron-001 (Trunsworth Greyvale)")
    print("Goal: Find and checkout 'The Burden of Lorde Tuskar'")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Search catalog for book
        print_step(1, "Searching catalog for 'Burden of Lorde Tuskar'")
        try:
            response = await client.get(
                f"{CATALOG_URL}/books",
                params={"title": "Burden of Lorde Tuskar"}
            )
            response.raise_for_status()
            books = response.json()

            if not books:
                print("  ❌ No books found!")
                return

            book = books[0]
            book_id = book["id"]
            print(f"  ✅ Found book: {book['title']}")
            print(f"     Book ID: {book_id}")
            print(f"     Author: {book['author']}")

        except Exception as e:
            print(f"  ❌ Error searching catalog: {e}")
            return

        # Step 2: Check availability
        print_step(2, f"Checking availability for book {book_id}")
        try:
            response = await client.get(
                f"{CATALOG_URL}/books/{book_id}/instances",
                params={"status": "available"}
            )
            response.raise_for_status()
            instances = response.json()

            if not instances:
                print("  ❌ No available copies!")
                return

            instance = instances[0]
            instance_id = instance["id"]
            print(f"  ✅ Found {len(instances)} available copy/copies")
            print(f"     Instance ID: {instance_id}")
            print(f"     Barcode: {instance.get('barcode')}")
            print(f"     Location: {instance.get('location')}")
            print(f"     Condition: {instance.get('condition')}")

        except Exception as e:
            print(f"  ❌ Error checking availability: {e}")
            return

        # Step 3: Verify patron exists in circulation service
        print_step(3, "Verifying patron in circulation service")
        patron_id = "patron-001"
        try:
            response = await client.get(f"{CIRCULATION_URL}/patrons/{patron_id}")
            response.raise_for_status()
            patron = response.json()
            print(f"  ✅ Patron verified: {patron['name']}")
            print(f"     Email: {patron['email']}")
            print(f"     Category: {patron['category']}")
            print(f"     Checkout limit: {patron['checkout_limit']}")
            print(f"     Blocked: {patron.get('blocked', False)}")

        except Exception as e:
            print(f"  ❌ Error verifying patron: {e}")
            return

        # Step 4: Create checkout
        print_step(4, "Creating checkout in circulation service")
        try:
            response = await client.post(
                f"{CIRCULATION_URL}/checkouts",
                json={
                    "patron_id": patron_id,
                    "instance_id": instance_id,
                }
            )
            response.raise_for_status()
            checkout = response.json()
            checkout_id = checkout["id"]
            print(f"  ✅ Checkout created successfully!")
            print(f"     Checkout ID: {checkout_id}")
            print(f"     Due date: {checkout['due_date']}")
            print(f"     Status: {checkout['status']}")

        except httpx.HTTPStatusError as e:
            print(f"  ❌ Checkout failed: {e.response.status_code}")
            print(f"     Error: {e.response.text}")
            return
        except Exception as e:
            print(f"  ❌ Error creating checkout: {e}")
            return

        # Step 5: Verify instance status updated
        print_step(5, "Verifying instance status updated in catalog")
        try:
            response = await client.get(f"{CATALOG_URL}/instances/{instance_id}")
            response.raise_for_status()
            updated_instance = response.json()
            print(f"  ✅ Instance status: {updated_instance['status']}")
            if updated_instance['status'] == 'checked_out':
                print("     Instance correctly marked as checked out!")
            else:
                print(f"     ⚠️  Warning: Expected 'checked_out', got '{updated_instance['status']}'")

        except Exception as e:
            print(f"  ⚠️  Could not verify instance status: {e}")

        # Step 6: Get patron's current checkouts
        print_step(6, "Retrieving patron's active checkouts")
        try:
            response = await client.get(
                f"{CIRCULATION_URL}/patrons/{patron_id}/checkouts",
                params={"status": "active"}
            )
            response.raise_for_status()
            checkouts = response.json()
            print(f"  ✅ Patron has {len(checkouts)} active checkout(s)")

            for co in checkouts:
                print(f"     - {co['id']}: Instance {co['instance_id']}, due {co['due_date']}")

        except Exception as e:
            print(f"  ⚠️  Could not retrieve checkouts: {e}")

    # Summary
    print_header("WORKFLOW COMPLETE")
    print(f"✅ Successfully checked out book '{book['title']}'")
    print(f"   Patron: {patron['name']}")
    print(f"   Checkout ID: {checkout_id}")
    print(f"   Due date: {checkout['due_date']}")
    print()


async def main():
    """Run the workflow test."""
    try:
        await test_complete_checkout_workflow()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
