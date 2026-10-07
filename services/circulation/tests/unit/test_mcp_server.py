"""Tests for Circulation MCP Server tools and resources.

These tests verify that the MCP server correctly:
- Exposes patron resources (details, summaries, fines)
- Executes tools (check eligibility, apply/remove blocks)
- Handles edge cases and errors
"""

import json
from datetime import datetime, timedelta, UTC

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from circulation.models import PatronModel, CheckoutModel, FineModel, HoldModel
from shared.constants import PatronCategory, CheckoutStatus, FineReason, HoldStatus


# =============================================================================
# Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def patron_good_standing(db_session):
    """Create a patron in good standing (no blocks, low fines)."""
    patron = PatronModel(
        id="patron-good-001",
        barcode="HAN-P-GOOD",
        name="Goodie Tusksworth",
        email="goodie@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,
    )
    db_session.add(patron)
    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def patron_with_fines(db_session):
    """Create a patron with moderate fines ($7.50 - between thresholds)."""
    patron = PatronModel(
        id="patron-fines-001",
        barcode="HAN-P-FINES",
        name="Finey McFineface",
        email="finey@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,
    )
    db_session.add(patron)

    # Add unpaid fines totaling $7.50
    fine1 = FineModel(
        id="fine-mcp-001",
        patron_id=patron.id,
        reason=FineReason.OVERDUE.value,
        amount=5.00,
        description="Test fine 1",
        paid=False,
        waived=False,
        created_at=datetime.now(UTC),
    )
    fine2 = FineModel(
        id="fine-mcp-002",
        patron_id=patron.id,
        reason=FineReason.OVERDUE.value,
        amount=2.50,
        description="Test fine 2",
        paid=False,
        waived=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(fine1)
    db_session.add(fine2)

    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def patron_high_fines(db_session):
    """Create a patron with high fines ($12.00 - above blocking threshold)."""
    patron = PatronModel(
        id="patron-high-fines-001",
        barcode="HAN-P-HIGHFINES",
        name="Heavy Finesworth",
        email="heavy@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,  # Not yet blocked, but should be
    )
    db_session.add(patron)

    # Add unpaid fine of $12.00
    fine = FineModel(
        id="fine-high-001",
        patron_id=patron.id,
        reason=FineReason.LOST.value,
        amount=12.00,
        description="Lost book replacement fee",
        paid=False,
        waived=False,
        created_at=datetime.now(UTC),
    )
    db_session.add(fine)

    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def patron_blocked(db_session):
    """Create a blocked patron."""
    patron = PatronModel(
        id="patron-blocked-001",
        barcode="HAN-P-BLOCKED",
        name="Blocky McBlockface",
        email="blocky@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=True,
        block_reason="Excessive overdue items",
    )
    db_session.add(patron)
    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def patron_at_checkout_limit(db_session):
    """Create a patron at their checkout limit."""
    patron = PatronModel(
        id="patron-limit-001",
        barcode="HAN-P-LIMIT",
        name="Limitless No More",
        email="limitless@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=3,  # Low limit for testing
        hold_limit=10,
        blocked=False,
    )
    db_session.add(patron)

    # Add 3 active checkouts
    for i in range(3):
        checkout = CheckoutModel(
            id=f"checkout-limit-{i}",
            instance_id=f"inst-limit-{i}",
            patron_id=patron.id,
            checked_out_at=datetime.now(UTC) - timedelta(days=5),
            due_date=datetime.now(UTC) + timedelta(days=9),
            status=CheckoutStatus.ACTIVE.value,
            renewals_used=0,
            max_renewals=2,
        )
        db_session.add(checkout)

    await db_session.commit()
    await db_session.refresh(patron)
    return patron


@pytest_asyncio.fixture
async def patron_with_overdue(db_session):
    """Create a patron with overdue checkouts."""
    patron = PatronModel(
        id="patron-overdue-001",
        barcode="HAN-P-OVERDUE",
        name="Tardy Tusk",
        email="tardy@hanno.lib",
        category=PatronCategory.ADULT.value,
        checkout_limit=10,
        hold_limit=10,
        blocked=False,
    )
    db_session.add(patron)

    # Add overdue checkout (status stays "active" until manually updated;
    # the MCP function detects overdue by due_date < now)
    checkout = CheckoutModel(
        id="checkout-overdue-mcp",
        instance_id="inst-overdue-001",
        patron_id=patron.id,
        checked_out_at=datetime.now(UTC) - timedelta(days=20),
        due_date=datetime.now(UTC) - timedelta(days=6),  # 6 days overdue
        status=CheckoutStatus.ACTIVE.value,  # Still "active" but past due
        renewals_used=0,
        max_renewals=2,
    )
    db_session.add(checkout)

    await db_session.commit()
    await db_session.refresh(patron)
    return patron


# =============================================================================
# Tests for Check Patron Eligibility Tool
# =============================================================================

class TestCheckPatronEligibility:
    """Tests for the check_patron_eligibility MCP tool."""

    @pytest.mark.asyncio
    async def test_eligible_patron_good_standing(self, db_session, patron_good_standing):
        """Patron in good standing should be eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility(patron_good_standing.id)

        data = json.loads(result)
        assert data["eligible"] is True
        assert data["patron_id"] == patron_good_standing.id
        assert data["total_fines"] == 0
        assert data["blocked"] is False
        assert data["issues"] is None

    @pytest.mark.asyncio
    async def test_ineligible_blocked_patron(self, db_session, patron_blocked):
        """Blocked patron should not be eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility(patron_blocked.id)

        data = json.loads(result)
        assert data["eligible"] is False
        assert data["blocked"] is True
        assert data["issues"] is not None
        assert any(i["type"] == "blocked" for i in data["issues"])

    @pytest.mark.asyncio
    async def test_ineligible_high_fines(self, db_session, patron_high_fines):
        """Patron with fines >= $10 should not be eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility(patron_high_fines.id)

        data = json.loads(result)
        assert data["eligible"] is False
        assert data["total_fines"] >= 10.00
        assert data["issues"] is not None
        assert any(i["type"] == "fines" for i in data["issues"])

    @pytest.mark.asyncio
    async def test_eligible_moderate_fines(self, db_session, patron_with_fines):
        """Patron with moderate fines (< $10) should be eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility(patron_with_fines.id)

        data = json.loads(result)
        # Moderate fines don't block eligibility (only >= $10 does)
        assert data["eligible"] is True
        assert 0 < data["total_fines"] < 10.00

    @pytest.mark.asyncio
    async def test_ineligible_at_checkout_limit(self, db_session, patron_at_checkout_limit):
        """Patron at checkout limit should not be eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility(patron_at_checkout_limit.id)

        data = json.loads(result)
        assert data["eligible"] is False
        assert data["active_checkouts"] >= data["checkout_limit"]
        assert any(i["type"] == "checkout_limit" for i in data["issues"])

    @pytest.mark.asyncio
    async def test_nonexistent_patron(self, db_session):
        """Checking non-existent patron should return not eligible."""
        from circulation.mcp_server import check_patron_eligibility

        result = await check_patron_eligibility("nonexistent-patron-id")

        data = json.loads(result)
        assert data["eligible"] is False
        assert "not found" in data["reason"].lower()


# =============================================================================
# Tests for Apply Block Tool
# =============================================================================

class TestApplyBlock:
    """Tests for the apply_block MCP tool."""

    @pytest.mark.asyncio
    async def test_apply_block_success(self, db_session, patron_good_standing):
        """Applying block should update patron status."""
        from circulation.mcp_server import apply_block

        result = await apply_block(
            patron_id=patron_good_standing.id,
            reason="Test blocking reason",
            librarian_id="test-librarian"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["patron_id"] == patron_good_standing.id
        assert data["blocked"] is True
        assert "test-librarian" in data["block_reason"]

    @pytest.mark.asyncio
    async def test_apply_block_nonexistent_patron(self, db_session):
        """Applying block to non-existent patron should fail."""
        from circulation.mcp_server import apply_block

        result = await apply_block(
            patron_id="nonexistent-patron",
            reason="Test reason",
            librarian_id="test-librarian"
        )

        data = json.loads(result)
        assert "error" in data
        assert "not found" in data["error"].lower()


# =============================================================================
# Tests for Remove Block Tool
# =============================================================================

class TestRemoveBlock:
    """Tests for the remove_block MCP tool."""

    @pytest.mark.asyncio
    async def test_remove_block_success(self, db_session, patron_blocked):
        """Removing block should update patron status."""
        from circulation.mcp_server import remove_block

        result = await remove_block(
            patron_id=patron_blocked.id,
            librarian_id="test-librarian",
            notes="Block removed after appeal"
        )

        data = json.loads(result)
        assert data["success"] is True
        assert data["patron_id"] == patron_blocked.id
        assert data["blocked"] is False

    @pytest.mark.asyncio
    async def test_remove_block_nonexistent_patron(self, db_session):
        """Removing block from non-existent patron should fail."""
        from circulation.mcp_server import remove_block

        result = await remove_block(
            patron_id="nonexistent-patron",
            librarian_id="test-librarian",
            notes=""
        )

        data = json.loads(result)
        assert "error" in data


# =============================================================================
# Tests for Calculate Patron Fines Tool
# =============================================================================

class TestCalculatePatronFines:
    """Tests for the calculate_patron_fines MCP tool."""

    @pytest.mark.asyncio
    async def test_calculate_fines_with_balance(self, db_session, patron_with_fines):
        """Calculating fines should return correct total and breakdown."""
        from circulation.mcp_server import calculate_patron_fines

        result = await calculate_patron_fines(patron_with_fines.id)

        data = json.loads(result)
        assert data["patron_id"] == patron_with_fines.id
        assert data["total_outstanding"] == 7.50
        assert data["fine_count"] == 2
        assert "by_reason" in data
        assert FineReason.OVERDUE.value in data["by_reason"]

    @pytest.mark.asyncio
    async def test_calculate_fines_no_balance(self, db_session, patron_good_standing):
        """Patron with no fines should return zero."""
        from circulation.mcp_server import calculate_patron_fines

        result = await calculate_patron_fines(patron_good_standing.id)

        data = json.loads(result)
        assert data["patron_id"] == patron_good_standing.id
        assert data["total_outstanding"] == 0
        assert data["fine_count"] == 0


# =============================================================================
# Tests for Get Overdue Checkouts Tool
# =============================================================================

class TestGetOverdueCheckouts:
    """Tests for the get_overdue_checkouts MCP tool."""

    @pytest.mark.asyncio
    async def test_get_overdue_with_results(self, db_session, patron_with_overdue):
        """Should return overdue checkouts with days overdue."""
        from circulation.mcp_server import get_overdue_checkouts

        result = await get_overdue_checkouts(patron_id=patron_with_overdue.id)

        data = json.loads(result)
        assert data["total_overdue"] >= 1
        assert len(data["checkouts"]) >= 1

        # Check the overdue checkout details
        checkout = data["checkouts"][0]
        assert checkout["patron_id"] == patron_with_overdue.id
        assert checkout["days_overdue"] > 0

    @pytest.mark.asyncio
    async def test_get_overdue_no_results(self, db_session, patron_good_standing):
        """Patron with no overdue items should return empty list."""
        from circulation.mcp_server import get_overdue_checkouts

        result = await get_overdue_checkouts(patron_id=patron_good_standing.id)

        data = json.loads(result)
        assert data["total_overdue"] == 0
        assert len(data["checkouts"]) == 0

    @pytest.mark.asyncio
    async def test_get_all_overdue(self, db_session, patron_with_overdue):
        """Getting all overdue (no patron filter) should work."""
        from circulation.mcp_server import get_overdue_checkouts

        result = await get_overdue_checkouts()  # No patron filter

        data = json.loads(result)
        assert "total_overdue" in data
        assert "checkouts" in data


# =============================================================================
# Tests for Patron Resource Access
# =============================================================================

class TestPatronResources:
    """Tests for patron resource data access."""

    @pytest.mark.asyncio
    async def test_get_patron_details(self, db_session, patron_with_fines):
        """Getting patron details should include all fields."""
        from circulation.mcp_server import get_patron

        result = await get_patron(patron_with_fines.id)

        data = json.loads(result)
        assert data["id"] == patron_with_fines.id
        assert data["name"] == patron_with_fines.name
        assert data["email"] == patron_with_fines.email
        assert "checkout_limit" in data
        assert "total_fines" in data
        assert data["total_fines"] == 7.50

    @pytest.mark.asyncio
    async def test_get_patron_not_found(self, db_session):
        """Getting non-existent patron should return error."""
        from circulation.mcp_server import get_patron

        result = await get_patron("nonexistent-id")

        data = json.loads(result)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_get_patron_summary(self, db_session, patron_with_overdue):
        """Getting patron summary should include checkouts, holds, fines."""
        from circulation.mcp_server import get_patron_summary

        result = await get_patron_summary(patron_with_overdue.id)

        data = json.loads(result)
        assert "patron" in data
        assert "checkouts" in data
        assert "holds" in data
        assert "fines" in data
        assert data["patron"]["id"] == patron_with_overdue.id

    @pytest.mark.asyncio
    async def test_get_patron_fines_resource(self, db_session, patron_with_fines):
        """Getting patron fines should return fine details."""
        from circulation.mcp_server import get_patron_fines

        result = await get_patron_fines(patron_with_fines.id)

        data = json.loads(result)
        assert data["patron_id"] == patron_with_fines.id
        assert data["total_unpaid"] == 7.50
        assert data["fine_count"] == 2
        assert len(data["fines"]) == 2


# =============================================================================
# Tests for Active Checkouts Resource
# =============================================================================

class TestActiveCheckoutsResource:
    """Tests for active checkouts resource."""

    @pytest.mark.asyncio
    async def test_get_active_checkouts(self, db_session, patron_at_checkout_limit):
        """Getting active checkouts should return all active items."""
        from circulation.mcp_server import get_active_checkouts

        result = await get_active_checkouts()

        data = json.loads(result)
        assert data["total"] >= 3  # patron_at_checkout_limit has 3 checkouts
        assert len(data["checkouts"]) >= 3

    @pytest.mark.asyncio
    async def test_active_checkouts_include_overdue_flag(self, db_session, patron_with_overdue):
        """Active checkouts should include is_overdue flag."""
        from circulation.mcp_server import get_active_checkouts

        result = await get_active_checkouts()

        data = json.loads(result)
        # Find the overdue checkout
        overdue_items = [c for c in data["checkouts"] if c.get("is_overdue")]
        assert len(overdue_items) >= 1
