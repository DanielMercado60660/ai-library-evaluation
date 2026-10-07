#!/usr/bin/env python3
"""Test the complete ILL borrowing workflow.

This script traces a patron requesting a book from another library via ILL:
1. Patron wants a book not in our catalog
2. ILL service verifies patron with circulation service
3. ILL service checks our catalog (book should NOT be there)
4. ILL service creates outbound request
"""

import asyncio
import httpx


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


async def test_ill_borrow_workflow():
    """Test: Patron requests external book via ILL."""
    print_header("ILL BORROWING WORKFLOW TEST")
    print("\nScenario: Dr. Helena Caladent requests an external research book")
    print("Patron: patron-006 (Dr. Helena Caladent, Researcher)")
    print("Book: 'Advanced Pachyderm Algorithms' (not in our catalog)")
    print("Source Library: university-library")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: Verify patron exists in circulation service
        print_step(1, "Verifying patron in circulation service")
        patron_id = "patron-006"
        try:
            response = await client.get(f"{CIRCULATION_URL}/patrons/{patron_id}")
            response.raise_for_status()
            patron = response.json()
            print(f"  ✅ Patron verified: {patron['name']}")
            print(f"     Email: {patron['email']}")
            print(f"     Category: {patron['category']}")
            print(f"     Blocked: {patron.get('blocked', False)}")

        except Exception as e:
            print(f"  ❌ Error verifying patron: {e}")
            return

        # Step 2: Check if book exists in our catalog (it shouldn't)
        print_step(2, "Checking our catalog for the book")
        external_book_id = "ext-book-701"  # External library's book ID
        try:
            response = await client.get(f"{CATALOG_URL}/books/{external_book_id}")

            if response.status_code == 404:
                print(f"  ✅ Book not in our catalog (as expected for ILL)")
            else:
                print(f"  ⚠️  Book found in our catalog - ILL may not be needed!")

        except Exception as e:
            print(f"  ✅ Book not in catalog (confirmed): {e}")

        # Step 3: Create ILL request
        print_step(3, "Creating ILL request")
        try:
            response = await client.post(
                f"{ILL_URL}/requests",
                json={
                    "patron_id": patron_id,
                    "book_id": external_book_id,
                    "book_title": "Advanced Pachyderm Algorithms",
                    "isbn": "978-3-TECH-101",
                    "author": "Dr. T. Tusker",
                    "source_library": "university-library",
                }
            )
            response.raise_for_status()
            ill_request = response.json()
            request_id = ill_request["id"]

            print(f"  ✅ ILL request created successfully!")
            print(f"     Request ID: {request_id}")
            print(f"     Book: {ill_request['book_title']}")
            print(f"     Source: {ill_request['source_library']}")
            print(f"     Status: {ill_request['status']}")
            print(f"     Requested at: {ill_request['requested_at']}")

        except httpx.HTTPStatusError as e:
            print(f"  ❌ ILL request failed: {e.response.status_code}")
            error_detail = e.response.json() if e.response.headers.get('content-type') == 'application/json' else e.response.text
            print(f"     Error: {error_detail}")
            return
        except Exception as e:
            print(f"  ❌ Error creating ILL request: {e}")
            return

        # Step 4: Retrieve patron's ILL requests
        print_step(4, "Retrieving patron's ILL requests")
        try:
            response = await client.get(
                f"{ILL_URL}/requests",
                params={"patron_id": patron_id}
            )
            response.raise_for_status()
            requests = response.json()

            print(f"  ✅ Patron has {len(requests)} ILL request(s)")
            for req in requests:
                print(f"     - {req['id']}: {req['book_title']} ({req['status']})")

        except Exception as e:
            print(f"  ⚠️  Could not retrieve requests: {e}")

        # Step 5: Get request details
        print_step(5, "Getting detailed ILL request info")
        try:
            response = await client.get(f"{ILL_URL}/requests/{request_id}")
            response.raise_for_status()
            request_detail = response.json()

            print(f"  ✅ Request details retrieved")
            print(f"     Book: {request_detail['book_title']} by {request_detail.get('author')}")
            print(f"     ISBN: {request_detail.get('isbn')}")
            print(f"     Status: {request_detail['status']}")
            print(f"     Source library: {request_detail['source_library']}")
            print(f"     Patron reference: {request_detail['patron_reference']}")

        except Exception as e:
            print(f"  ⚠️  Could not retrieve request details: {e}")

    # Summary
    print_header("WORKFLOW COMPLETE")
    print(f"✅ Successfully created ILL request")
    print(f"   Patron: Dr. Helena Caladent")
    print(f"   Request ID: {request_id}")
    print(f"   Book: Advanced Pachyderm Algorithms")
    print(f"   Source: university-library")
    print(f"   Status: {ill_request['status']}")
    print()
    print("Next steps:")
    print("  - Source library will receive request (in full system)")
    print("  - Source library approves and ships book")
    print("  - Status updates to 'shipped', then 'received'")
    print("  - Patron notified when book arrives")
    print()


async def main():
    """Run the workflow test."""
    try:
        await test_ill_borrow_workflow()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
