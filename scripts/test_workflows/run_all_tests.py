#!/usr/bin/env python3
"""Run all workflow tests in sequence.

This script runs all manual workflow tests to verify end-to-end integration:
1. Checkout workflow
2. ILL borrowing workflow
3. ILL lending workflow
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from test_checkout_workflow import test_complete_checkout_workflow
from test_ill_borrow_workflow import test_ill_borrow_workflow
from test_ill_lend_workflow import test_ill_lend_workflow


async def run_all_workflows():
    """Run all workflow tests."""
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "HANNO MEMORIAL LIBRARY SYSTEM" + " " * 23 + "║")
    print("║" + " " * 17 + "End-to-End Workflow Tests" + " " * 25 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    tests = [
        ("Checkout Workflow", test_complete_checkout_workflow),
        ("ILL Borrowing Workflow", test_ill_borrow_workflow),
        ("ILL Lending Workflow", test_ill_lend_workflow),
    ]

    results = []

    for test_name, test_func in tests:
        print(f"\n\n{'▶' * 35}")
        print(f"Running: {test_name}")
        print(f"{'▶' * 35}\n")

        try:
            await test_func()
            results.append((test_name, True, None))
            print(f"\n✅ {test_name} PASSED")
        except Exception as e:
            results.append((test_name, False, str(e)))
            print(f"\n❌ {test_name} FAILED: {e}")

        # Wait a bit between tests
        await asyncio.sleep(2)

    # Print summary
    print("\n\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 25 + "TEST SUMMARY" + " " * 31 + "║")
    print("╚" + "═" * 68 + "╝")
    print()

    passed = sum(1 for _, success, _ in results if success)
    failed = len(results) - passed

    for test_name, success, error in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {status}: {test_name}")
        if error:
            print(f"           Error: {error}")

    print()
    print(f"Total: {len(results)} tests, {passed} passed, {failed} failed")
    print()

    if failed > 0:
        print("⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)
    else:
        print("🎉 All tests passed!")


async def main():
    """Entry point."""
    try:
        await run_all_workflows()
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
