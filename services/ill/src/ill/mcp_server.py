"""MCP Server for ILL Service.

This MCP server exposes ILL database resources and tools for AI agents.
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

from ill.db import async_engine, get_session
from ill.models import ILLRequestModel, InboundLoanModel, ILLAuditTrail
from shared.constants import ILLRequestStatus, InboundLoanStatus

# Configure logging to stderr (not stdout, which would corrupt MCP messages)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("ill-mcp-server")


# =============================================================================
# Resources - Read-only data access
# =============================================================================

@mcp.resource("ill://queue/pending/outbound")
async def get_pending_outbound_queue() -> str:
    """Get all pending outbound ILL requests awaiting approval.

    Returns enriched data including:
    - Request details (book, patron, priority)
    - Days pending review
    - Patron justification
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel)
            .where(ILLRequestModel.status == ILLRequestStatus.PENDING_APPROVAL)
            .order_by(ILLRequestModel.requested_at.asc())
        )
        requests = result.scalars().all()

        queue_items = []
        now = datetime.now(UTC)

        for req in requests:
            req_time = req.requested_at.replace(tzinfo=UTC) if req.requested_at.tzinfo is None else req.requested_at
            days_pending = (now - req_time).days

            queue_items.append({
                "id": req.id,
                "book_id": req.book_id,
                "book_title": req.book_title,
                "isbn": req.isbn,
                "author": req.author,
                "patron_id": req.patron_id,
                "patron_reference": req.patron_reference,
                "source_library": req.source_library,
                "priority": req.priority,
                "patron_justification": req.patron_justification,
                "requested_at": req.requested_at.isoformat() if req.requested_at else None,
                "days_pending": days_pending,
                "notes": req.notes,
            })

        return json.dumps({
            "total": len(queue_items),
            "items": queue_items
        }, indent=2)


@mcp.resource("ill://queue/pending/inbound")
async def get_pending_inbound_queue() -> str:
    """Get all pending inbound loan requests awaiting approval.

    Returns data for lending decisions including:
    - Instance and book details
    - Requesting library info
    - Days pending review
    """
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(InboundLoanModel)
            .where(InboundLoanModel.status == InboundLoanStatus.PENDING_APPROVAL)
            .order_by(InboundLoanModel.requested_at.asc())
        )
        loans = result.scalars().all()

        queue_items = []
        now = datetime.now(UTC)

        for loan in loans:
            loan_time = loan.requested_at.replace(tzinfo=UTC) if loan.requested_at.tzinfo is None else loan.requested_at
            days_pending = (now - loan_time).days

            queue_items.append({
                "id": loan.id,
                "instance_id": loan.instance_id,
                "book_id": loan.book_id,
                "requesting_library": loan.requesting_library,
                "patron_reference": loan.patron_reference,  # Opaque - don't look up
                "requested_at": loan.requested_at.isoformat() if loan.requested_at else None,
                "loan_period_days": loan.loan_period_days,
                "days_pending": days_pending,
            })

        return json.dumps({
            "total": len(queue_items),
            "items": queue_items
        }, indent=2)


@mcp.resource("ill://request/{request_id}")
async def get_request_details(request_id: str) -> str:
    """Get detailed information about a specific ILL request."""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        req = result.scalar_one_or_none()

        if not req:
            return json.dumps({"error": f"Request {request_id} not found"})

        return json.dumps({
            "id": req.id,
            "book_id": req.book_id,
            "book_title": req.book_title,
            "isbn": req.isbn,
            "author": req.author,
            "patron_id": req.patron_id,
            "patron_reference": req.patron_reference,
            "source_library": req.source_library,
            "status": req.status,
            "priority": req.priority,
            "patron_justification": req.patron_justification,
            "approved_by": req.approved_by,
            "approved_at": req.approved_at.isoformat() if req.approved_at else None,
            "denied_by": req.denied_by,
            "denied_at": req.denied_at.isoformat() if req.denied_at else None,
            "requested_at": req.requested_at.isoformat() if req.requested_at else None,
            "shipped_at": req.shipped_at.isoformat() if req.shipped_at else None,
            "received_at": req.received_at.isoformat() if req.received_at else None,
            "due_date": req.due_date.isoformat() if req.due_date else None,
            "returned_to_lender_at": req.returned_to_lender_at.isoformat() if req.returned_to_lender_at else None,
            "notes": req.notes,
            "denial_reason": req.denial_reason,
            "loan_period_days": req.loan_period_days,
        }, indent=2)


@mcp.resource("ill://loan/{loan_id}")
async def get_inbound_loan_details(loan_id: str) -> str:
    """Get detailed information about a specific inbound loan."""
    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == loan_id)
        )
        loan = result.scalar_one_or_none()

        if not loan:
            return json.dumps({"error": f"Loan {loan_id} not found"})

        return json.dumps({
            "id": loan.id,
            "instance_id": loan.instance_id,
            "book_id": loan.book_id,
            "requesting_library": loan.requesting_library,
            "patron_reference": loan.patron_reference,
            "status": loan.status,
            "approved_by": loan.approved_by,
            "denied_by": loan.denied_by,
            "decision_notes": loan.decision_notes,
            "requested_at": loan.requested_at.isoformat() if loan.requested_at else None,
            "approved_at": loan.approved_at.isoformat() if loan.approved_at else None,
            "shipped_at": loan.shipped_at.isoformat() if loan.shipped_at else None,
            "due_date": loan.due_date.isoformat() if loan.due_date else None,
            "returned_at": loan.returned_at.isoformat() if loan.returned_at else None,
            "loan_period_days": loan.loan_period_days,
        }, indent=2)


@mcp.resource("ill://audit/{request_id}")
async def get_audit_trail(request_id: str) -> str:
    """Get audit trail for an ILL request or inbound loan."""
    async with AsyncSession(async_engine) as session:
        # Check if this is an outbound request or inbound loan
        result = await session.execute(
            select(ILLAuditTrail)
            .where(
                (ILLAuditTrail.request_id == request_id) |
                (ILLAuditTrail.loan_id == request_id)
            )
            .order_by(ILLAuditTrail.changed_at.asc())
        )
        audit_entries = result.scalars().all()

        entries = []
        for entry in audit_entries:
            entries.append({
                "id": entry.id,
                "request_id": entry.request_id,
                "loan_id": entry.loan_id,
                "request_type": entry.request_type,
                "from_status": entry.from_status,
                "to_status": entry.to_status,
                "changed_by": entry.changed_by,
                "change_reason": entry.change_reason,
                "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
                "extra_data": entry.extra_data,
            })

        return json.dumps({
            "request_id": request_id,
            "total_entries": len(entries),
            "entries": entries
        }, indent=2)


# =============================================================================
# Tools - Actions that modify state
# =============================================================================

@mcp.tool()
async def approve_ill_request(
    request_id: str,
    librarian_id: str,
    notes: str = ""
) -> str:
    """Approve an outbound ILL request.

    Transitions the request from PENDING_APPROVAL to REQUESTED status.

    Args:
        request_id: The ID of the ILL request to approve
        librarian_id: The ID of the librarian/agent approving the request
        notes: Optional notes explaining the approval decision

    Returns:
        JSON with the updated request details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError
    from datetime import timedelta

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one_or_none()

        if not ill_request:
            return json.dumps({"error": f"Request {request_id} not found"})

        if ill_request.status != ILLRequestStatus.PENDING_APPROVAL:
            return json.dumps({
                "error": f"Cannot approve request with status '{ill_request.status}'. Must be 'pending_approval'."
            })

        # Use state machine to transition
        state_manager = StateManager(session)

        try:
            ill_request, side_effects = await state_manager.transition_outbound_request(
                ill_request,
                ILLRequestStatus.REQUESTED.value,
                changed_by=librarian_id,
                change_reason=notes or "Request approved via MCP agent",
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        # Update approval metadata
        now = datetime.now(UTC)
        ill_request.approved_by = librarian_id
        ill_request.approved_at = now

        if notes:
            ill_request.notes = f"{ill_request.notes or ''}\n[Approved by {librarian_id}]: {notes}".strip()

        await session.commit()
        await session.refresh(ill_request)

        return json.dumps({
            "success": True,
            "request_id": ill_request.id,
            "new_status": ill_request.status,
            "approved_by": librarian_id,
            "approved_at": now.isoformat(),
            "side_effects": side_effects,
        }, indent=2)


@mcp.tool()
async def deny_ill_request(
    request_id: str,
    librarian_id: str,
    reason: str
) -> str:
    """Deny an outbound ILL request.

    Transitions the request from PENDING_APPROVAL to DENIED status.

    Args:
        request_id: The ID of the ILL request to deny
        librarian_id: The ID of the librarian/agent denying the request
        reason: The reason for denial (required)

    Returns:
        JSON with the updated request details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError

    if not reason:
        return json.dumps({"error": "Denial reason is required"})

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one_or_none()

        if not ill_request:
            return json.dumps({"error": f"Request {request_id} not found"})

        if ill_request.status != ILLRequestStatus.PENDING_APPROVAL:
            return json.dumps({
                "error": f"Cannot deny request with status '{ill_request.status}'. Must be 'pending_approval'."
            })

        # Use state machine to transition
        state_manager = StateManager(session)

        try:
            ill_request, side_effects = await state_manager.transition_outbound_request(
                ill_request,
                ILLRequestStatus.DENIED.value,
                changed_by=librarian_id,
                change_reason=reason,
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        # Update denial metadata
        now = datetime.now(UTC)
        ill_request.denied_by = librarian_id
        ill_request.denied_at = now
        ill_request.denial_reason = reason

        await session.commit()
        await session.refresh(ill_request)

        return json.dumps({
            "success": True,
            "request_id": ill_request.id,
            "new_status": ill_request.status,
            "denied_by": librarian_id,
            "denied_at": now.isoformat(),
            "denial_reason": reason,
        }, indent=2)


@mcp.tool()
async def approve_inbound_loan(
    loan_id: str,
    librarian_id: str,
    notes: str = ""
) -> str:
    """Approve an inbound loan request (lending to another library).

    Transitions the loan from PENDING_APPROVAL to APPROVED status.

    Args:
        loan_id: The ID of the inbound loan to approve
        librarian_id: The ID of the librarian/agent approving the loan
        notes: Optional notes explaining the approval decision

    Returns:
        JSON with the updated loan details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError
    from datetime import timedelta

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == loan_id)
        )
        inbound_loan = result.scalar_one_or_none()

        if not inbound_loan:
            return json.dumps({"error": f"Loan {loan_id} not found"})

        if inbound_loan.status != InboundLoanStatus.PENDING_APPROVAL:
            return json.dumps({
                "error": f"Cannot approve loan with status '{inbound_loan.status}'. Must be 'pending_approval'."
            })

        # Use state machine to transition
        state_manager = StateManager(session)

        try:
            inbound_loan, side_effects = await state_manager.transition_inbound_loan(
                inbound_loan,
                InboundLoanStatus.APPROVED.value,
                changed_by=librarian_id,
                change_reason=notes or "Loan approved via MCP agent",
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        # Update approval metadata
        now = datetime.now(UTC)
        inbound_loan.approved_by = librarian_id
        inbound_loan.approved_at = now
        inbound_loan.decision_notes = notes
        inbound_loan.due_date = now + timedelta(days=inbound_loan.loan_period_days)

        await session.commit()
        await session.refresh(inbound_loan)

        return json.dumps({
            "success": True,
            "loan_id": inbound_loan.id,
            "new_status": inbound_loan.status,
            "approved_by": librarian_id,
            "approved_at": now.isoformat(),
            "due_date": inbound_loan.due_date.isoformat(),
            "side_effects": side_effects,
        }, indent=2)


@mcp.tool()
async def deny_inbound_loan(
    loan_id: str,
    librarian_id: str,
    reason: str
) -> str:
    """Deny an inbound loan request (refuse to lend to another library).

    Transitions the loan from PENDING_APPROVAL to DENIED status.

    Args:
        loan_id: The ID of the inbound loan to deny
        librarian_id: The ID of the librarian/agent denying the loan
        reason: The reason for denial (required)

    Returns:
        JSON with the updated loan details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError

    if not reason:
        return json.dumps({"error": "Denial reason is required"})

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(InboundLoanModel).where(InboundLoanModel.id == loan_id)
        )
        inbound_loan = result.scalar_one_or_none()

        if not inbound_loan:
            return json.dumps({"error": f"Loan {loan_id} not found"})

        if inbound_loan.status != InboundLoanStatus.PENDING_APPROVAL:
            return json.dumps({
                "error": f"Cannot deny loan with status '{inbound_loan.status}'. Must be 'pending_approval'."
            })

        # Use state machine to transition
        state_manager = StateManager(session)

        try:
            inbound_loan, side_effects = await state_manager.transition_inbound_loan(
                inbound_loan,
                InboundLoanStatus.DENIED.value,
                changed_by=librarian_id,
                change_reason=reason,
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        # Update denial metadata
        now = datetime.now(UTC)
        inbound_loan.denied_by = librarian_id
        inbound_loan.decision_notes = reason

        await session.commit()
        await session.refresh(inbound_loan)

        return json.dumps({
            "success": True,
            "loan_id": inbound_loan.id,
            "new_status": inbound_loan.status,
            "denied_by": librarian_id,
            "denial_reason": reason,
        }, indent=2)


@mcp.tool()
async def query_audit_trail(
    request_id: str | None = None,
    loan_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None
) -> str:
    """Query the audit trail for compliance and debugging.

    Args:
        request_id: Filter by outbound request ID (optional)
        loan_id: Filter by inbound loan ID (optional)
        from_date: Start date filter in ISO format (optional)
        to_date: End date filter in ISO format (optional)

    Returns:
        JSON with matching audit trail entries
    """
    async with AsyncSession(async_engine) as session:
        query = select(ILLAuditTrail)

        if request_id:
            query = query.where(ILLAuditTrail.request_id == request_id)
        if loan_id:
            query = query.where(ILLAuditTrail.loan_id == loan_id)
        if from_date:
            try:
                from_dt = datetime.fromisoformat(from_date)
                query = query.where(ILLAuditTrail.changed_at >= from_dt)
            except ValueError:
                return json.dumps({"error": f"Invalid from_date format: {from_date}"})
        if to_date:
            try:
                to_dt = datetime.fromisoformat(to_date)
                query = query.where(ILLAuditTrail.changed_at <= to_dt)
            except ValueError:
                return json.dumps({"error": f"Invalid to_date format: {to_date}"})

        query = query.order_by(ILLAuditTrail.changed_at.desc()).limit(100)

        result = await session.execute(query)
        audit_entries = result.scalars().all()

        entries = []
        for entry in audit_entries:
            entries.append({
                "id": entry.id,
                "request_id": entry.request_id,
                "loan_id": entry.loan_id,
                "request_type": entry.request_type,
                "from_status": entry.from_status,
                "to_status": entry.to_status,
                "changed_by": entry.changed_by,
                "change_reason": entry.change_reason,
                "changed_at": entry.changed_at.isoformat() if entry.changed_at else None,
                "extra_data": entry.extra_data,
            })

        return json.dumps({
            "total_entries": len(entries),
            "entries": entries
        }, indent=2)


@mcp.tool()
async def get_queue_statistics() -> str:
    """Get statistics about the current approval queues.

    Returns counts and metrics for both outbound and inbound queues.
    """
    async with AsyncSession(async_engine) as session:
        # Count pending outbound requests
        outbound_pending = await session.execute(
            select(func.count(ILLRequestModel.id))
            .where(ILLRequestModel.status == ILLRequestStatus.PENDING_APPROVAL)
        )
        outbound_count = outbound_pending.scalar()

        # Count pending inbound loans
        inbound_pending = await session.execute(
            select(func.count(InboundLoanModel.id))
            .where(InboundLoanModel.status == InboundLoanStatus.PENDING_APPROVAL)
        )
        inbound_count = inbound_pending.scalar()

        # Get priority breakdown for outbound
        priority_result = await session.execute(
            select(ILLRequestModel.priority, func.count(ILLRequestModel.id))
            .where(ILLRequestModel.status == ILLRequestStatus.PENDING_APPROVAL)
            .group_by(ILLRequestModel.priority)
        )
        priority_breakdown = {row[0]: row[1] for row in priority_result.all()}

        return json.dumps({
            "outbound_pending": outbound_count,
            "inbound_pending": inbound_count,
            "total_pending": outbound_count + inbound_count,
            "outbound_by_priority": priority_breakdown,
        }, indent=2)


@mcp.tool()
async def create_ill_request(
    book_id: str,
    patron_id: str,
    source_library: str,
    isbn: str = "",
    priority: str = "normal",
    patron_justification: str = "",
    notes: str = ""
) -> str:
    """Create an outbound ILL request for a book from another library.

    Args:
        book_id: The ID of the book being requested
        patron_id: The ID of the patron making the request
        source_library: The library code of the lending library
        isbn: Optional ISBN of the book
        priority: Priority level (normal, rush, faculty)
        patron_justification: Patron's reason for needing the book
        notes: Additional notes

    Returns:
        JSON with the created request details or error message
    """
    from uuid import uuid4

    async with AsyncSession(async_engine) as session:
        # Check for duplicate active requests
        dup_result = await session.execute(
            select(func.count(ILLRequestModel.id))
            .where(
                ILLRequestModel.book_id == book_id,
                ILLRequestModel.patron_id == patron_id,
                ILLRequestModel.status.in_([
                    ILLRequestStatus.PENDING_APPROVAL,
                    ILLRequestStatus.REQUESTED,
                    ILLRequestStatus.APPROVED,
                    ILLRequestStatus.SHIPPED,
                    ILLRequestStatus.RECEIVED,
                    ILLRequestStatus.IN_USE,
                ])
            )
        )
        if (dup_result.scalar() or 0) > 0:
            return json.dumps({"error": "An active ILL request for this book already exists"})

        now = datetime.now(UTC)
        ill_request = ILLRequestModel(
            id=f"ill-req-{uuid4().hex[:12]}",
            book_id=book_id,
            book_title=f"Book {book_id}",
            patron_id=patron_id,
            patron_reference=f"HAN-P-{patron_id.split('-')[-1].zfill(3)}",
            source_library=source_library,
            status=ILLRequestStatus.REQUESTED,
            priority=priority,
            patron_justification=patron_justification,
            requested_at=now,
            notes=notes,
            loan_period_days=28,
        )
        if isbn:
            ill_request.isbn = isbn

        session.add(ill_request)
        await session.commit()
        await session.refresh(ill_request)

        return json.dumps({
            "success": True,
            "request_id": ill_request.id,
            "book_id": book_id,
            "patron_id": patron_id,
            "source_library": source_library,
            "status": ill_request.status,
        }, indent=2)


@mcp.tool()
async def mark_request_received(request_id: str) -> str:
    """Mark an ILL request as received (item arrived from lending library).

    Args:
        request_id: The ID of the ILL request

    Returns:
        JSON with updated request details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one_or_none()
        if not ill_request:
            return json.dumps({"error": f"Request {request_id} not found"})

        if ill_request.status != ILLRequestStatus.SHIPPED:
            return json.dumps({"error": f"Cannot mark as received - current status is '{ill_request.status}'"})

        state_manager = StateManager(session)
        try:
            ill_request, side_effects = await state_manager.transition_outbound_request(
                ill_request,
                ILLRequestStatus.RECEIVED.value,
                changed_by="mcp-agent",
                change_reason="Item received via MCP",
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        ill_request.received_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(ill_request)

        return json.dumps({
            "success": True,
            "request_id": ill_request.id,
            "new_status": ill_request.status,
            "received_at": ill_request.received_at.isoformat(),
        }, indent=2)


@mcp.tool()
async def return_to_lender(request_id: str) -> str:
    """Mark an ILL item as returned to the lending library.

    Args:
        request_id: The ID of the ILL request

    Returns:
        JSON with updated request details or error message
    """
    from ill.state_machine import StateManager, InvalidTransitionError

    async with AsyncSession(async_engine) as session:
        result = await session.execute(
            select(ILLRequestModel).where(ILLRequestModel.id == request_id)
        )
        ill_request = result.scalar_one_or_none()
        if not ill_request:
            return json.dumps({"error": f"Request {request_id} not found"})

        if ill_request.status not in (ILLRequestStatus.IN_USE, ILLRequestStatus.RECEIVED):
            return json.dumps({"error": f"Cannot return - current status is '{ill_request.status}'"})

        state_manager = StateManager(session)
        try:
            ill_request, side_effects = await state_manager.transition_outbound_request(
                ill_request,
                ILLRequestStatus.RETURNED.value,
                changed_by="mcp-agent",
                change_reason="Item returned to lender via MCP",
            )
        except InvalidTransitionError as e:
            return json.dumps({"error": str(e)})

        ill_request.returned_to_lender_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(ill_request)

        return json.dumps({
            "success": True,
            "request_id": ill_request.id,
            "new_status": ill_request.status,
            "returned_at": ill_request.returned_to_lender_at.isoformat(),
        }, indent=2)


def main():
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
