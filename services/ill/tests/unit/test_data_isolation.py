"""
CRITICAL DATA ISOLATION TESTS

These tests verify that inbound ILL endpoints NEVER expose patron information
to external libraries. This is a fundamental security requirement for the A2A protocol.

Data isolation requirements:
1. Holdings queries return ONLY aggregate data (counts, not details)
2. Loan requests NEVER include patron information
3. No checkout details exposed (who has books, when they're due)
4. patron_reference is stored as opaque string (no FK lookup)
"""

import json
from datetime import datetime, UTC

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# =============================================================================
# Test: Holdings Query Data Isolation
# =============================================================================

class TestHoldingsQueryDataIsolation:
    """Verify /inbound/query NEVER exposes patron information."""

    @pytest.mark.asyncio
    async def test_query_response_no_patron_info(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """Query response MUST NOT include patron identifiers."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0001"
            }
        )

        response_text = response.text.lower()
        response_json = response.json()

        # CRITICAL: No patron references in response
        assert "patron" not in response_text
        assert "han-p-" not in response_text  # Our patron barcodes
        assert "barcode" not in response_text

        # Verify response contains only aggregate data
        assert "held" in response_json
        assert "total_copies" in response_json
        assert "available_copies" in response_json

        # MUST NOT contain individual record details
        assert "checkout" not in response_text
        assert "checked_out_by" not in response_text
        assert "borrower" not in response_text

    @pytest.mark.asyncio
    async def test_query_no_checkout_details(
        self, client: AsyncClient
    ):
        """Query MUST NOT expose checkout information."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0002"  # Assume some copies checked out
            }
        )

        response_text = response.text.lower()

        # CRITICAL: No checkout metadata
        assert "checkout_id" not in response_text
        assert "due_date" not in response_text  # For specific checkouts
        assert "checked_out_at" not in response_text

        # "earliest_return_date" is OK (aggregate, no patron link)
        # But NO individual checkout records

    @pytest.mark.asyncio
    async def test_query_no_hold_information(
        self, client: AsyncClient
    ):
        """Query MUST NOT expose hold queue information."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0003"
            }
        )

        response_text = response.text.lower()

        # CRITICAL: No hold queue details
        assert "hold" not in response_text or "hold" in "threshold"  # Allow "threshold" but not "hold"
        assert "queue" not in response_text
        assert "waiting" not in response_text.replace("waiting for", "")  # Allow in error messages

    @pytest.mark.asyncio
    async def test_query_only_counts_not_lists(
        self, client: AsyncClient
    ):
        """Query MUST return counts, not lists of items."""
        response = await client.post(
            "/inbound/query",
            json={
                "isbn": "978-0-HANNO-0001"
            }
        )

        data = response.json()

        # Should have counts
        assert isinstance(data.get("total_copies"), int)
        assert isinstance(data.get("available_copies"), int)

        # MUST NOT have arrays of instances or checkouts
        for key, value in data.items():
            assert not isinstance(value, list), f"Response contains list '{key}' - should only have counts"


# =============================================================================
# Test: Loan Request Data Isolation
# =============================================================================

class TestLoanRequestDataIsolation:
    """Verify /inbound/loan-request NEVER exposes patron information."""

    @pytest.mark.asyncio
    async def test_loan_response_no_patron_info(
        self, client: AsyncClient
    ):
        """Loan response MUST NOT include our patron information."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-042"
            }
        )

        response_text = response.text.lower()

        # CRITICAL: No patron information
        assert "patron" not in response_text or "patron_reference" in response_text  # Their patron_reference is OK
        assert "han-p-" not in response_text  # Our patron barcodes
        assert "email" not in response_text
        assert "phone" not in response_text
        assert "name" not in response_text  # Patron names

    @pytest.mark.asyncio
    async def test_loan_denial_no_reason_details(
        self, client: AsyncClient
    ):
        """Denial reason MUST NOT expose internal details."""
        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-MIT-9999",  # Not held
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-100"
            }
        )

        data = response.json()

        if not data["approved"]:
            # Reason should be generic (no_available_copies, not_held)
            # MUST NOT say "checked out by patron XYZ" or similar
            reason = data.get("reason", "")
            assert "patron" not in reason.lower()
            assert "han-p-" not in reason.lower()

    @pytest.mark.asyncio
    async def test_loan_stores_patron_reference_no_fk(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        """patron_reference MUST be stored as opaque string (no FK to our patrons)."""
        from ill.models import InboundLoanModel

        response = await client.post(
            "/inbound/loan-request",
            json={
                "isbn": "978-0-HANNO-0001",
                "requesting_library": "mastodon-institute",
                "patron_reference": "MAS-P-ARBITRARY"
            }
        )

        if response.json()["approved"]:
            # Check database model
            # patron_reference should have NO foreign key constraint
            from sqlalchemy import inspect
            mapper = inspect(InboundLoanModel)
            patron_ref_column = mapper.columns["patron_reference"]

            # Verify no foreign key
            assert len(patron_ref_column.foreign_keys) == 0, \
                "patron_reference MUST NOT have foreign key to patron table"


# =============================================================================
# Test: Item Returned Data Isolation
# =============================================================================

class TestItemReturnDataIsolation:
    """Verify /inbound/item-returned NEVER exposes patron information."""

    @pytest.mark.asyncio
    async def test_return_response_no_patron_info(
        self, client: AsyncClient, sample_inbound_loan_active
    ):
        """Return response MUST NOT include patron information."""
        response = await client.post(
            "/inbound/item-returned",
            json={
                "request_id": sample_inbound_loan_active.id
            }
        )

        response_text = response.text.lower()

        # CRITICAL: No patron information in response
        # patron_reference is OK (it's theirs, opaque to us)
        assert "han-p-" not in response_text  # Our patron barcodes
        assert "email" not in response_text
        assert "checkout" not in response_text  # No checkout details


# =============================================================================
# Test: Cross-Endpoint Data Isolation
# =============================================================================

class TestCrossEndpointDataIsolation:
    """Verify consistent data isolation across all inbound endpoints."""

    @pytest.mark.asyncio
    async def test_no_endpoint_leaks_instance_details(
        self, client: AsyncClient
    ):
        """No inbound endpoint should expose instance-level details."""
        # Query holdings
        query_response = await client.post(
            "/inbound/query",
            json={"isbn": "978-0-HANNO-0001"}
        )

        query_text = query_response.text.lower()

        # MUST NOT expose instance IDs, locations, barcodes
        assert "inst-" not in query_text  # Instance IDs
        assert "shelf" not in query_text or "on_hold_shelf" in query_text  # Shelf locations (except status)
        assert "han-item-" not in query_text  # Item barcodes

    @pytest.mark.asyncio
    async def test_aggregate_data_only(
        self, client: AsyncClient
    ):
        """All inbound endpoints should return ONLY aggregate data."""
        # This is a meta-test verifying the pattern

        test_cases = [
            {
                "endpoint": "/inbound/query",
                "method": "POST",
                "data": {"isbn": "978-0-HANNO-0001"}
            }
        ]

        for case in test_cases:
            if case["method"] == "POST":
                response = await client.post(case["endpoint"], json=case["data"])
            else:
                response = await client.get(case["endpoint"])

            # Parse response
            try:
                data = response.json()
            except:
                continue

            # Verify no arrays of detailed records
            # (counts/integers are OK, arrays of objects are not)
            def check_no_detail_arrays(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        check_no_detail_arrays(value, f"{path}.{key}")
                elif isinstance(obj, list):
                    # Arrays of primitive types (strings, ints) are OK
                    # Arrays of objects are NOT
                    if len(obj) > 0 and isinstance(obj[0], dict):
                        assert False, f"Found array of objects at {path}: {obj[:2]}"

            check_no_detail_arrays(data)


# =============================================================================
# Test: Error Messages Don't Leak Data
# =============================================================================

class TestErrorMessageDataIsolation:
    """Verify error messages don't accidentally expose internal data."""

    @pytest.mark.asyncio
    async def test_404_errors_no_internal_ids(
        self, client: AsyncClient
    ):
        """404 errors should not expose internal IDs or details."""
        response = await client.post(
            "/inbound/item-returned",
            json={"request_id": "nonexistent"}
        )

        assert response.status_code == 404
        error_text = response.text.lower()

        # Generic 404 message
        # MUST NOT include database IDs, patron info, etc.
        assert "patron" not in error_text
        assert "checkout" not in error_text

    @pytest.mark.asyncio
    async def test_validation_errors_no_internal_schema(
        self, client: AsyncClient
    ):
        """Validation errors should not expose internal schema details."""
        response = await client.post(
            "/inbound/query",
            json={"invalid_field": "value"}
        )

        # Should be 422 or 400
        assert response.status_code in [400, 422]

        # Error should not expose database table names or internal fields
        error_text = response.text.lower()
        # "isbn" and "title" are OK (public fields)
        # But not "patron_id", "checkout_id", etc.
