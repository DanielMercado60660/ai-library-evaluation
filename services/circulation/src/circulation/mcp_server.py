"""MCP Server for Circulation Service.

This MCP server exposes patron, checkout, hold, and fine resources/tools for AI agents.
It runs alongside the FastAPI HTTP server and provides direct database access
via the Model Context Protocol.
"""

import logging
import json
from datetime import datetime, UTC
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from circulation.db import async_engine
from circulation.models import PatronModel, CheckoutModel, HoldModel, FineModel, BookInstanceModel

# Configure logging to stderr (not stdout, which would corrupt MCP messages)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("circulation-mcp-server")


# =============================================================================
# Resources - Read-only data access
# =============================================================================

@mcp.resource("patron://{patron_id}")
async def get_patron(patron_id: str) -> str:
    """Get detailed information about a patron.

    Includes account status, blocked status, checkout/hold limits.
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = result.scalar_one_or_none()

        if not patron:
            return json.dumps({"error": f"Patron {patron_id} not found"})

        # Get checkout and fine counts
        checkouts_result = await session.execute(
            select(func.count(CheckoutModel.id))
            .where(CheckoutModel.patron_id == patron_id)
            .where(CheckoutModel.status == "active")
        )
        active_checkouts = checkouts_result.scalar() or 0

        fines_result = await session.execute(
            select(func.sum(FineModel.amount))
            .where(FineModel.patron_id == patron_id)
            .where(FineModel.paid == False)
            .where(FineModel.waived == False)
        )
        total_fines = fines_result.scalar() or 0.0

        holds_result = await session.execute(
            select(func.count(HoldModel.id))
            .where(HoldModel.patron_id == patron_id)
            .where(HoldModel.status.in_(["pending", "ready"]))
        )
        active_holds = holds_result.scalar() or 0

        return json.dumps({
            "id": patron.id,
            "barcode": patron.barcode,
            "name": patron.name,
            "email": patron.email,
            "phone": patron.phone,
            "category": patron.category,
            "checkout_limit": patron.checkout_limit,
            "hold_limit": patron.hold_limit,
            "blocked": patron.blocked,
            "block_reason": patron.block_reason,
            "created_at": patron.created_at.isoformat() if patron.created_at else None,
            "active_checkouts": active_checkouts,
            "active_holds": active_holds,
            "total_fines": round(total_fines, 2),
        }, indent=2)


@mcp.resource("patron://{patron_id}/summary")
async def get_patron_summary(patron_id: str) -> str:
    """Get comprehensive summary of patron's account.

    Includes checkouts, holds, and fines with full details.
    """
    async with AsyncSession(async_engine) as session:
        # Get patron
        patron_result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = patron_result.scalar_one_or_none()

        if not patron:
            return json.dumps({"error": f"Patron {patron_id} not found"})

        # Get active checkouts
        checkouts_result = await session.execute(
            select(CheckoutModel)
            .where(CheckoutModel.patron_id == patron_id)
            .where(CheckoutModel.status == "active")
            .order_by(CheckoutModel.due_date.asc())
        )
        checkouts = checkouts_result.scalars().all()

        # Get active holds
        holds_result = await session.execute(
            select(HoldModel)
            .where(HoldModel.patron_id == patron_id)
            .where(HoldModel.status.in_(["pending", "ready"]))
            .order_by(HoldModel.created_at.asc())
        )
        holds = holds_result.scalars().all()

        # Get unpaid fines
        fines_result = await session.execute(
            select(FineModel)
            .where(FineModel.patron_id == patron_id)
            .where(FineModel.paid == False)
            .where(FineModel.waived == False)
            .order_by(FineModel.created_at.desc())
        )
        fines = fines_result.scalars().all()

        total_fines = sum(f.amount for f in fines)

        return json.dumps({
            "patron": {
                "id": patron.id,
                "name": patron.name,
                "email": patron.email,
                "category": patron.category,
                "blocked": patron.blocked,
                "block_reason": patron.block_reason,
            },
            "checkouts": [
                {
                    "id": c.id,
                    "instance_id": c.instance_id,
                    "checked_out_at": c.checked_out_at.isoformat() if c.checked_out_at else None,
                    "due_date": c.due_date.isoformat() if c.due_date else None,
                    "renewals_used": c.renewals_used,
                    "max_renewals": c.max_renewals,
                    "is_overdue": (c.due_date.replace(tzinfo=UTC) if c.due_date.tzinfo is None else c.due_date) < datetime.now(UTC) if c.due_date else False,
                }
                for c in checkouts
            ],
            "holds": [
                {
                    "id": h.id,
                    "book_id": h.book_id,
                    "position": h.position,
                    "status": h.status,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "expires_at": h.expires_at.isoformat() if h.expires_at else None,
                }
                for h in holds
            ],
            "fines": [
                {
                    "id": f.id,
                    "reason": f.reason,
                    "amount": f.amount,
                    "description": f.description,
                    "created_at": f.created_at.isoformat() if f.created_at else None,
                }
                for f in fines
            ],
            "total_fines": round(total_fines, 2),
            "checkouts_count": len(checkouts),
            "holds_count": len(holds),
            "fines_count": len(fines),
        }, indent=2)


@mcp.resource("checkout://active")
async def get_active_checkouts() -> str:
    """Get all active checkouts across all patrons.

    Useful for monitoring overdue items.
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(CheckoutModel)
            .where(CheckoutModel.status == "active")
            .order_by(CheckoutModel.due_date.asc())
        )
        checkouts = result.scalars().all()

        now = datetime.now(UTC)
        checkout_list = []

        for c in checkouts:
            due_date = c.due_date.replace(tzinfo=UTC) if c.due_date and c.due_date.tzinfo is None else c.due_date
            is_overdue = due_date < now if due_date else False
            days_overdue = (now - due_date).days if is_overdue else 0

            checkout_list.append({
                "id": c.id,
                "instance_id": c.instance_id,
                "patron_id": c.patron_id,
                "checked_out_at": c.checked_out_at.isoformat() if c.checked_out_at else None,
                "due_date": c.due_date.isoformat() if c.due_date else None,
                "renewals_used": c.renewals_used,
                "is_overdue": is_overdue,
                "days_overdue": days_overdue,
            })

        return json.dumps({
            "total": len(checkout_list),
            "checkouts": checkout_list
        }, indent=2)


@mcp.resource("fine://patron/{patron_id}")
async def get_patron_fines(patron_id: str) -> str:
    """Get all unpaid fines for a patron."""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(FineModel)
            .where(FineModel.patron_id == patron_id)
            .where(FineModel.paid == False)
            .where(FineModel.waived == False)
            .order_by(FineModel.created_at.desc())
        )
        fines = result.scalars().all()

        fine_list = []
        for f in fines:
            fine_list.append({
                "id": f.id,
                "checkout_id": f.checkout_id,
                "reason": f.reason,
                "amount": f.amount,
                "description": f.description,
                "created_at": f.created_at.isoformat() if f.created_at else None,
            })

        total = sum(f.amount for f in fines)

        return json.dumps({
            "patron_id": patron_id,
            "total_unpaid": round(total, 2),
            "fine_count": len(fine_list),
            "fines": fine_list
        }, indent=2)


# =============================================================================
# Tools - Actions that modify state
# =============================================================================

@mcp.tool()
async def check_patron_eligibility(patron_id: str) -> str:
    """Check if a patron is eligible for ILL or new checkouts.

    Checks for:
    - Account blocked status
    - Outstanding fines above threshold ($10)
    - Checkout limit

    Args:
        patron_id: The ID of the patron to check

    Returns:
        JSON with eligibility status and reasons
    """
    async with AsyncSession(async_engine) as session:
        # Get patron
        patron_result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = patron_result.scalar_one_or_none()

        if not patron:
            return json.dumps({
                "eligible": False,
                "patron_id": patron_id,
                "reason": "Patron not found"
            })

        issues = []

        # Check if blocked
        if patron.blocked:
            issues.append({
                "type": "blocked",
                "message": f"Account blocked: {patron.block_reason or 'No reason provided'}"
            })

        # Check fines
        fines_result = await session.execute(
            select(func.sum(FineModel.amount))
            .where(FineModel.patron_id == patron_id)
            .where(FineModel.paid == False)
            .where(FineModel.waived == False)
        )
        total_fines = fines_result.scalar() or 0.0

        if total_fines >= 10.00:
            issues.append({
                "type": "fines",
                "message": f"Outstanding fines exceed limit: ${total_fines:.2f}"
            })

        # Check checkout count
        checkouts_result = await session.execute(
            select(func.count(CheckoutModel.id))
            .where(CheckoutModel.patron_id == patron_id)
            .where(CheckoutModel.status == "active")
        )
        active_checkouts = checkouts_result.scalar() or 0

        if active_checkouts >= patron.checkout_limit:
            issues.append({
                "type": "checkout_limit",
                "message": f"At checkout limit: {active_checkouts}/{patron.checkout_limit}"
            })

        eligible = len(issues) == 0

        return json.dumps({
            "eligible": eligible,
            "patron_id": patron_id,
            "patron_name": patron.name,
            "total_fines": round(total_fines, 2),
            "active_checkouts": active_checkouts,
            "checkout_limit": patron.checkout_limit,
            "blocked": patron.blocked,
            "issues": issues if issues else None
        }, indent=2)


@mcp.tool()
async def apply_block(
    patron_id: str,
    reason: str,
    librarian_id: str
) -> str:
    """Apply a block to a patron's account.

    Args:
        patron_id: The ID of the patron to block
        reason: The reason for blocking
        librarian_id: The ID of the librarian applying the block

    Returns:
        JSON with the updated patron status
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = result.scalar_one_or_none()

        if not patron:
            return json.dumps({"error": f"Patron {patron_id} not found"})

        patron.blocked = True
        patron.block_reason = f"{reason} (blocked by {librarian_id})"

        await session.commit()
        await session.refresh(patron)

        return json.dumps({
            "success": True,
            "patron_id": patron.id,
            "blocked": patron.blocked,
            "block_reason": patron.block_reason
        }, indent=2)


@mcp.tool()
async def remove_block(
    patron_id: str,
    librarian_id: str,
    notes: str = ""
) -> str:
    """Remove a block from a patron's account.

    Args:
        patron_id: The ID of the patron to unblock
        librarian_id: The ID of the librarian removing the block
        notes: Optional notes about why the block was removed

    Returns:
        JSON with the updated patron status
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = result.scalar_one_or_none()

        if not patron:
            return json.dumps({"error": f"Patron {patron_id} not found"})

        patron.blocked = False
        patron.block_reason = None

        await session.commit()
        await session.refresh(patron)

        return json.dumps({
            "success": True,
            "patron_id": patron.id,
            "blocked": patron.blocked,
            "removed_by": librarian_id,
            "notes": notes
        }, indent=2)


@mcp.tool()
async def calculate_patron_fines(patron_id: str) -> str:
    """Calculate total outstanding fines for a patron.

    Args:
        patron_id: The ID of the patron

    Returns:
        JSON with fine breakdown by type and total
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(FineModel)
            .where(FineModel.patron_id == patron_id)
            .where(FineModel.paid == False)
            .where(FineModel.waived == False)
        )
        fines = result.scalars().all()

        # Group by reason
        by_reason = {}
        for fine in fines:
            if fine.reason not in by_reason:
                by_reason[fine.reason] = {"count": 0, "total": 0.0}
            by_reason[fine.reason]["count"] += 1
            by_reason[fine.reason]["total"] += fine.amount

        total = sum(f.amount for f in fines)

        return json.dumps({
            "patron_id": patron_id,
            "total_outstanding": round(total, 2),
            "fine_count": len(fines),
            "by_reason": {k: {"count": v["count"], "total": round(v["total"], 2)} for k, v in by_reason.items()}
        }, indent=2)


@mcp.tool()
async def get_overdue_checkouts(patron_id: str | None = None) -> str:
    """Get all overdue checkouts, optionally filtered by patron.

    Args:
        patron_id: Optional patron ID to filter by

    Returns:
        JSON with list of overdue checkouts and days overdue
    """
    async with AsyncSession(async_engine) as session:
        now = datetime.now(UTC)

        query = select(CheckoutModel).where(
            CheckoutModel.status == "active",
            CheckoutModel.due_date < now
        )

        if patron_id:
            query = query.where(CheckoutModel.patron_id == patron_id)

        query = query.order_by(CheckoutModel.due_date.asc())

        result = await session.execute(query)
        checkouts = result.scalars().all()

        overdue_list = []
        for c in checkouts:
            due_date = c.due_date.replace(tzinfo=UTC) if c.due_date and c.due_date.tzinfo is None else c.due_date
            days_overdue = (now - due_date).days if due_date else 0

            overdue_list.append({
                "checkout_id": c.id,
                "instance_id": c.instance_id,
                "patron_id": c.patron_id,
                "due_date": c.due_date.isoformat() if c.due_date else None,
                "days_overdue": days_overdue,
                "renewals_used": c.renewals_used,
                "max_renewals": c.max_renewals,
            })

        return json.dumps({
            "total_overdue": len(overdue_list),
            "checkouts": overdue_list
        }, indent=2)


@mcp.tool()
async def checkout_item(instance_id: str, patron_id: str) -> str:
    """Check out a book instance to a patron.

    Args:
        instance_id: The ID of the book instance to check out
        patron_id: The ID of the patron checking out the item

    Returns:
        JSON with checkout details or error message
    """
    from uuid import uuid4
    from datetime import timedelta
    from shared.constants import DEFAULT_LOAN_DAYS, DEFAULT_MAX_RENEWALS

    async with AsyncSession(async_engine) as session:
        # Verify patron
        patron_result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = patron_result.scalar_one_or_none()
        if not patron:
            return json.dumps({"error": "Patron not found"})
        if patron.blocked:
            return json.dumps({"error": f"Patron is blocked: {patron.block_reason}"})

        # Check checkout limit
        active_count = await session.execute(
            select(func.count(CheckoutModel.id))
            .where(CheckoutModel.patron_id == patron_id, CheckoutModel.status == "active")
        )
        if (active_count.scalar() or 0) >= patron.checkout_limit:
            return json.dumps({"error": "Checkout limit reached"})

        # Verify instance
        inst_result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
        )
        instance = inst_result.scalar_one_or_none()
        if not instance:
            return json.dumps({"error": "Item not found"})
        if instance.status != "available":
            return json.dumps({"error": f"Item not available (status: {instance.status})"})

        # Create checkout
        now = datetime.now(UTC)
        checkout = CheckoutModel(
            id=f"checkout-{uuid4().hex[:12]}",
            instance_id=instance_id,
            patron_id=patron_id,
            checked_out_at=now,
            due_date=now + timedelta(days=DEFAULT_LOAN_DAYS),
            status="active",
            renewals_used=0,
            max_renewals=DEFAULT_MAX_RENEWALS,
        )
        instance.status = "checked_out"

        session.add(checkout)
        await session.commit()
        await session.refresh(checkout)

        return json.dumps({
            "success": True,
            "checkout_id": checkout.id,
            "instance_id": instance_id,
            "patron_id": patron_id,
            "due_date": checkout.due_date.isoformat(),
            "renewals_remaining": checkout.max_renewals,
        }, indent=2)


@mcp.tool()
async def return_item(instance_id: str, dropbox: bool = False) -> str:
    """Return a checked-out book instance.

    Args:
        instance_id: The ID of the book instance being returned
        dropbox: Whether the item was returned via dropbox

    Returns:
        JSON with return details or error message
    """
    async with AsyncSession(async_engine) as session:
        # Find instance
        inst_result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == instance_id)
        )
        instance = inst_result.scalar_one_or_none()
        if not instance:
            return json.dumps({"error": "Item not found"})

        # Find active checkout
        checkout_result = await session.execute(
            select(CheckoutModel)
            .where(CheckoutModel.instance_id == instance_id, CheckoutModel.status == "active")
        )
        checkout = checkout_result.scalar_one_or_none()
        if not checkout:
            return json.dumps({"error": "No active checkout for this item"})

        # Process return
        now = datetime.now(UTC)
        checkout.returned_at = now
        checkout.status = "returned"
        instance.status = "available"

        # Calculate overdue fine
        fine_amount = 0.0
        due = checkout.due_date.replace(tzinfo=UTC) if checkout.due_date.tzinfo is None else checkout.due_date
        if now > due:
            days_overdue = (now - due).days
            fine_amount = round(days_overdue * 0.25, 2)
            if fine_amount > 0:
                from uuid import uuid4
                fine = FineModel(
                    id=f"fine-{uuid4().hex[:12]}",
                    patron_id=checkout.patron_id,
                    checkout_id=checkout.id,
                    reason="overdue",
                    amount=fine_amount,
                    description=f"Overdue by {days_overdue} days",
                    created_at=now,
                )
                session.add(fine)

        await session.commit()

        return json.dumps({
            "success": True,
            "checkout_id": checkout.id,
            "returned_at": now.isoformat(),
            "dropbox": dropbox,
            "fines_incurred": fine_amount,
        }, indent=2)


@mcp.tool()
async def place_hold(book_id: str, patron_id: str) -> str:
    """Place a hold on a book for a patron.

    Args:
        book_id: The ID of the book to hold
        patron_id: The ID of the patron placing the hold

    Returns:
        JSON with hold details or error message
    """
    from uuid import uuid4

    async with AsyncSession(async_engine) as session:
        # Verify patron
        patron_result = await session.execute(
            select(PatronModel).where(PatronModel.id == patron_id)
        )
        patron = patron_result.scalar_one_or_none()
        if not patron:
            return json.dumps({"error": "Patron not found"})
        if patron.blocked:
            return json.dumps({"error": f"Patron is blocked: {patron.block_reason}"})

        # Check hold limit
        hold_count = await session.execute(
            select(func.count(HoldModel.id))
            .where(HoldModel.patron_id == patron_id, HoldModel.status.in_(["pending", "ready"]))
        )
        if (hold_count.scalar() or 0) >= patron.hold_limit:
            return json.dumps({"error": "Hold limit reached"})

        # Check for duplicate
        dup = await session.execute(
            select(func.count(HoldModel.id))
            .where(HoldModel.patron_id == patron_id, HoldModel.book_id == book_id, HoldModel.status.in_(["pending", "ready"]))
        )
        if (dup.scalar() or 0) > 0:
            return json.dumps({"error": "Patron already has an active hold on this book"})

        # Calculate position
        pos_result = await session.execute(
            select(func.count(HoldModel.id))
            .where(HoldModel.book_id == book_id, HoldModel.status.in_(["pending", "ready"]))
        )
        position = (pos_result.scalar() or 0) + 1

        hold = HoldModel(
            id=f"hold-{uuid4().hex[:12]}",
            book_id=book_id,
            patron_id=patron_id,
            position=position,
            status="pending",
            created_at=datetime.now(UTC),
        )
        session.add(hold)
        await session.commit()
        await session.refresh(hold)

        return json.dumps({
            "success": True,
            "hold_id": hold.id,
            "book_id": book_id,
            "patron_id": patron_id,
            "position": position,
        }, indent=2)


@mcp.tool()
async def cancel_hold(hold_id: str) -> str:
    """Cancel an existing hold.

    Args:
        hold_id: The ID of the hold to cancel

    Returns:
        JSON with cancellation details or error message
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(HoldModel).where(HoldModel.id == hold_id)
        )
        hold = result.scalar_one_or_none()
        if not hold:
            return json.dumps({"error": "Hold not found"})

        if hold.status not in ("pending", "ready"):
            return json.dumps({"error": f"Cannot cancel hold with status '{hold.status}'"})

        hold.status = "cancelled"
        await session.commit()

        return json.dumps({
            "success": True,
            "hold_id": hold_id,
            "status": "cancelled",
        }, indent=2)


@mcp.tool()
async def pay_fine(fine_id: str, amount: float) -> str:
    """Pay a fine.

    Args:
        fine_id: The ID of the fine to pay
        amount: The payment amount (must cover full fine)

    Returns:
        JSON with payment details or error message
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(FineModel).where(FineModel.id == fine_id)
        )
        fine = result.scalar_one_or_none()
        if not fine:
            return json.dumps({"error": "Fine not found"})
        if fine.paid:
            return json.dumps({"error": "Fine already paid"})
        if amount < fine.amount:
            return json.dumps({"error": f"Full payment of ${fine.amount:.2f} required"})

        fine.paid = True
        fine.paid_at = datetime.now(UTC)
        await session.commit()

        return json.dumps({
            "success": True,
            "fine_id": fine_id,
            "amount_paid": fine.amount,
            "remaining_balance": 0.0,
        }, indent=2)


@mcp.tool()
async def renew_checkout(checkout_id: str) -> str:
    """Renew an active checkout.

    Args:
        checkout_id: The ID of the checkout to renew

    Returns:
        JSON with renewal details or error message
    """
    from datetime import timedelta
    from shared.constants import DEFAULT_LOAN_DAYS

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(CheckoutModel).where(CheckoutModel.id == checkout_id)
        )
        checkout = result.scalar_one_or_none()
        if not checkout:
            return json.dumps({"error": "Checkout not found"})
        if checkout.status != "active":
            return json.dumps({"error": f"Cannot renew {checkout.status} checkout"})
        if checkout.renewals_used >= checkout.max_renewals:
            return json.dumps({"error": "No renewals remaining"})

        # Check for holds on this book
        inst_result = await session.execute(
            select(BookInstanceModel).where(BookInstanceModel.id == checkout.instance_id)
        )
        instance = inst_result.scalar_one_or_none()
        if instance:
            hold_count = await session.execute(
                select(func.count(HoldModel.id))
                .where(HoldModel.book_id == instance.book_id, HoldModel.status.in_(["pending", "ready"]))
            )
            if (hold_count.scalar() or 0) > 0:
                return json.dumps({"error": "Cannot renew - book has active holds"})

        checkout.renewals_used += 1
        now = datetime.now(UTC)
        checkout.due_date = now + timedelta(days=DEFAULT_LOAN_DAYS)
        await session.commit()
        await session.refresh(checkout)

        return json.dumps({
            "success": True,
            "checkout_id": checkout_id,
            "new_due_date": checkout.due_date.isoformat(),
            "renewals_remaining": checkout.max_renewals - checkout.renewals_used,
        }, indent=2)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
