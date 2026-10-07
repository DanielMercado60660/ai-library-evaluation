#!/usr/bin/env python3
"""Test the complete ILL lending workflow.

This script traces an inbound ILL request from another library:
1. External library queries our holdings
2. We have the book available
3. External library requests loan
4. We approve and create inbound loan record
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


async def test_ill_lend_workflow():
    """Test: External library queries and borrows one of our books."""
    print_header("ILL LENDING WORKFLOW TEST")
    print("\nScenario: Mastodon Institute Library requests a book from us")
    print("Requesting Library: mastodon-institute-library")
    print("Book: 'The Burden of Lorde Tuskar' (ISBN: 978-0-HANNO-0001)")
    print("Their Patron: MAST-P-042 (opaque to us)")

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Step 1: External library queries our holdings
        print_step(1, "External library queries our holdings")
        isbn = "978-0-HANNO-0001"
        try:
            response = await client.post(
                f"{ILL_URL}/inbound/query",
                json={
                    "isbn": isbn,
                    "title": None,  # Could search by title instead
                }
            )
            response.raise_for_status()
            holdings = response.json()

            print(f"  ✅ Holdings query successful")
            print(f"     Held: {holdings['held']}")
            print(f"     Total copies: {holdings['total_copies']}")
            print(f"     Available copies: {holdings['available_copies']}")
            print(f"     Loanable: {holdings['loanable']}")

            if holdings.get('loan_period_days'):
                print(f"     Loan period: {holdings['loan_period_days']} days")

            if not holdings['loanable']:
                print(f"  ⚠️  Book not loanable!")
                if holdings.get('earliest_return_date'):
                    print(f"     Earliest return: {holdings['earliest_return_date']}")
                return

        except httpx.HTTPStatusError as e:
            print(f"  ❌ Holdings query failed: {e.response.status_code}")
            print(f"     Error: {e.response.text}")
            return
        except Exception as e:
            print(f"  ❌ Error querying holdings: {e}")
            return

        # Step 2: External library requests loan
        print_step(2, "External library requests loan")
        try:
            response = await client.post(
                f"{ILL_URL}/inbound/loan-request",
                json={
                    "isbn": isbn,
                    "requesting_library": "mastodon-institute-library",
                    "patron_reference": "MAST-P-042",  # Their patron ID (opaque to us)
                }
            )
            response.raise_for_status()
            loan_response = response.json()

            if loan_response['approved']:
                print(f"  ✅ Loan request approved!")
                print(f"     Loan ID: {loan_response['loan_id']}")
                print(f"     Due date: {loan_response['due_date']}")
                print(f"     Loan period: {loan_response['loan_period_days']} days")
                loan_id = loan_response['loan_id']
            else:
                print(f"  ❌ Loan request denied")
                print(f"     Reason: {loan_response.get('reason')}")
                return

        except httpx.HTTPStatusError as e:
            print(f"  ❌ Loan request failed: {e.response.status_code}")
            print(f"     Error: {e.response.text}")
            return
        except Exception as e:
            print(f"  ❌ Error requesting loan: {e}")
            return

        # Step 3: Retrieve loan details
        print_step(3, "Retrieving inbound loan details")
        try:
            response = await client.get(f"{ILL_URL}/inbound/loans/{loan_id}")
            response.raise_for_status()
            loan = response.json()

            print(f"  ✅ Loan details retrieved")
            print(f"     Loan ID: {loan['id']}")
            print(f"     Book ID: {loan['book_id']}")
            print(f"     Instance ID: {loan['instance_id']}")
            print(f"     Requesting library: {loan['requesting_library']}")
            print(f"     Patron reference: {loan['patron_reference']}")
            print(f"     Status: {loan['status']}")
            print(f"     Due date: {loan['due_date']}")

        except Exception as e:
            print(f"  ⚠️  Could not retrieve loan details: {e}")

        # Step 4: List all our inbound loans
        print_step(4, "Listing all active inbound loans")
        try:
            response = await client.get(
                f"{ILL_URL}/inbound/loans",
                params={"status": "active"}
            )
            response.raise_for_status()
            loans = response.json()

            print(f"  ✅ Active inbound loans: {len(loans)}")
            for loan_item in loans:
                print(f"     - {loan_item['id']}: {loan_item['requesting_library']} "
                      f"(due {loan_item['due_date']})")

        except Exception as e:
            print(f"  ⚠️  Could not retrieve loans list: {e}")

        # Step 5: Verify instance reserved in catalog
        print_step(5, "Verifying instance status in catalog")
        try:
            instance_id = loan['instance_id']
            response = await client.get(f"{CATALOG_URL}/instances/{instance_id}")

            if response.status_code == 200:
                instance = response.json()
                print(f"  ✅ Instance status: {instance['status']}")
                if instance['status'] in ['ill_shipped', 'on_loan', 'unavailable']:
                    print("     Instance correctly marked as unavailable")
                else:
                    print(f"     ⚠️  Instance still shows as: {instance['status']}")
            else:
                print(f"  ⚠️  Could not retrieve instance (status {response.status_code})")

        except Exception as e:
            print(f"  ⚠️  Could not verify instance: {e}")

    # Summary
    print_header("WORKFLOW COMPLETE")
    print(f"✅ Successfully approved and created inbound loan")
    print(f"   Loan ID: {loan_id}")
    print(f"   Requesting library: mastodon-institute-library")
    print(f"   Book ISBN: {isbn}")
    print(f"   Due date: {loan_response['due_date']}")
    print()
    print("Next steps:")
    print("  - Ship book to requesting library")
    print("  - Update status to 'shipped'")
    print("  - When returned, update status to 'returned'")
    print("  - Instance becomes available again")
    print()


async def main():
    """Run the workflow test."""
    try:
        await test_ill_lend_workflow()
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
