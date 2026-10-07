"""API routes for the circulation service."""

import json
import logging
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from circulation.db import get_session
from circulation.models import (
    PatronModel,
    BookInstanceModel,
    CheckoutModel,
    HoldModel,
    FineModel,
)
from shared.eval.admin_seed import eval_mode_enabled

_logger = logging.getLogger(__name__)
from circulation.schemas import (
    HealthResponse,
    PatronResponse,
    PatronSummaryResponse,
    CheckoutRequest,
    CheckoutResponse,
    ReturnRequest,
    ReturnResponse,
    RenewalResponse,
    HoldRequest,
    HoldResponse,
    FineListResponse,
    FinePaymentRequest,
    FinePaymentResponse,
    BlockPatronRequest,
    BlockPatronResponse,
    UnblockPatronResponse,
)
from circulation.utils import get_book_title, process_hold_queue
from shared.schemas import Patron, Checkout, Hold, Fine
from shared.http_client import call_catalog, ServiceNotFoundError, ServiceUnavailableError
from shared.constants import (
    InstanceStatus,
    CheckoutStatus,
    HoldStatus,
    PatronCategory,
    FineReason,
    DEFAULT_LOAN_DAYS,
    DEFAULT_MAX_RENEWALS,
    DEFAULT_HOLD_EXPIRY_DAYS,
    FINE_RATE_PER_DAY,
    MAX_FINE_BEFORE_BLOCK,
    PATRON_LOAN_RULES,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for the circulation service."""
    return HealthResponse(
        status="healthy",
        service="circulation",
        version="0.1.0",
        library="Hanno Memorial Library",
    )


# =============================================================================
# Patron Endpoints
# =============================================================================

@router.get("/patrons", response_model=list[Patron])
async def list_patrons(
    session: AsyncSession = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
):
    """List all patrons."""
    result = await session.execute(
        select(PatronModel).offset(skip).limit(limit)
    )
    patrons = result.scalars().all()
    
    return [
        Patron(
            id=p.id,
            barcode=p.barcode,
            name=p.name,
            email=p.email,
            phone=p.phone,
            category=PatronCategory(p.category),
            checkout_limit=p.checkout_limit,
            hold_limit=p.hold_limit,
            blocked=p.blocked,
            block_reason=p.block_reason,
        )
        for p in patrons
    ]

@router.get("/patrons/{patron_id}", response_model=PatronResponse)
async def get_patron(
    patron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get patron details."""
    result = await session.execute(
        select(PatronModel).where(PatronModel.id == patron_id)
    )
    patron = result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    # Count current checkouts
    checkouts_result = await session.execute(
        select(func.count()).where(
            CheckoutModel.patron_id == patron_id,
            CheckoutModel.status == "active",
        )
    )
    current_checkouts = checkouts_result.scalar() or 0

    # Count active holds
    holds_result = await session.execute(
        select(func.count()).where(
            HoldModel.patron_id == patron_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    active_holds = holds_result.scalar() or 0

    # Calculate fines owed
    fines_result = await session.execute(
        select(func.sum(FineModel.amount)).where(
            FineModel.patron_id == patron_id,
            FineModel.paid == False,
            FineModel.waived == False,
        )
    )
    fines_owed = Decimal(str(fines_result.scalar() or 0))

    return PatronResponse(
        patron=Patron(
            id=patron.id,
            barcode=patron.barcode,
            name=patron.name,
            email=patron.email,
            phone=patron.phone,
            category=PatronCategory(patron.category),
            checkout_limit=patron.checkout_limit,
            hold_limit=patron.hold_limit,
            blocked=patron.blocked,
            block_reason=patron.block_reason,
        ),
        current_checkouts=current_checkouts,
        active_holds=active_holds,
        fines_owed=fines_owed,
    )


@router.get("/patrons/{patron_id}/summary", response_model=PatronSummaryResponse)
async def get_patron_summary(
    patron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get comprehensive patron summary with checkouts, holds, and fines."""
    # Get patron
    result = await session.execute(
        select(PatronModel).where(PatronModel.id == patron_id)
    )
    patron = result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    # Get checkouts
    checkouts_result = await session.execute(
        select(CheckoutModel).where(
            CheckoutModel.patron_id == patron_id,
            CheckoutModel.status.in_(["active", "overdue"]),
        )
    )
    checkouts = checkouts_result.scalars().all()

    # Get holds
    holds_result = await session.execute(
        select(HoldModel).where(
            HoldModel.patron_id == patron_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    holds = holds_result.scalars().all()

    # Get unpaid fines
    fines_result = await session.execute(
        select(FineModel).where(
            FineModel.patron_id == patron_id,
            FineModel.paid == False,
            FineModel.waived == False,
        )
    )
    fines = fines_result.scalars().all()

    total_fines = sum(Decimal(str(f.amount)) for f in fines)

    return PatronSummaryResponse(
        patron=Patron(
            id=patron.id,
            barcode=patron.barcode,
            name=patron.name,
            email=patron.email,
            phone=patron.phone,
            category=PatronCategory(patron.category),
            checkout_limit=patron.checkout_limit,
            hold_limit=patron.hold_limit,
            blocked=patron.blocked,
            block_reason=patron.block_reason,
        ),
        checkouts=[
            Checkout(
                id=c.id,
                instance_id=c.instance_id,
                patron_id=c.patron_id,
                checked_out_at=c.checked_out_at,
                due_date=c.due_date,
                returned_at=c.returned_at,
                status=CheckoutStatus(c.status),
            )
            for c in checkouts
        ],
        holds=[
            Hold(
                id=h.id,
                book_id=h.book_id,
                patron_id=h.patron_id,
                position=h.position,
                status=HoldStatus(h.status),
                created_at=h.created_at,
                notified_at=h.notified_at,
                expires_at=h.expires_at,
            )
            for h in holds
        ],
        fines=[
            Fine(
                id=f.id,
                patron_id=f.patron_id,
                checkout_id=f.checkout_id,
                reason=FineReason(f.reason),
                amount=Decimal(str(f.amount)),
                description=f.description,
                paid=f.paid,
                paid_at=f.paid_at,
                waived=f.waived,
                waived_reason=f.waived_reason,
                created_at=f.created_at,
            )
            for f in fines
        ],
        total_fines_owed=total_fines,
    )


@router.patch("/patrons/{patron_id}/block", response_model=BlockPatronResponse)
async def block_patron(
    patron_id: str,
    request: BlockPatronRequest,
    session: AsyncSession = Depends(get_session),
):
    """Manually block a patron with a reason."""
    if not request.reason or not request.reason.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_BLOCK_REASON", "message": "Block reason must not be empty"}
        )

    result = await session.execute(
        select(PatronModel).where(PatronModel.id == patron_id)
    )
    patron = result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    patron.blocked = True
    patron.block_reason = request.reason.strip()
    session.add(patron)
    await session.commit()

    return BlockPatronResponse(
        patron_id=patron.id,
        blocked=True,
        block_reason=patron.block_reason,
    )


@router.patch("/patrons/{patron_id}/unblock", response_model=UnblockPatronResponse)
async def unblock_patron(
    patron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Unblock a patron."""
    result = await session.execute(
        select(PatronModel).where(PatronModel.id == patron_id)
    )
    patron = result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    patron.blocked = False
    patron.block_reason = None
    session.add(patron)
    await session.commit()

    return UnblockPatronResponse(
        patron_id=patron.id,
        blocked=False,
    )


# =============================================================================
# Checkout Endpoints
# =============================================================================

@router.post("/checkouts", response_model=CheckoutResponse)
async def checkout_item(
    request: CheckoutRequest,
    session: AsyncSession = Depends(get_session),
):
    """Checkout an item to a patron."""
    # Verify patron exists and is not blocked
    patron_result = await session.execute(
        select(PatronModel).where(PatronModel.id == request.patron_id)
    )
    patron = patron_result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    if patron.blocked:
        raise HTTPException(
            status_code=400,
            detail={"code": "PATRON_BLOCKED", "message": patron.block_reason or "Patron is blocked"}
        )

    # Check fines
    fines_result = await session.execute(
        select(func.sum(FineModel.amount)).where(
            FineModel.patron_id == request.patron_id,
            FineModel.paid == False,
            FineModel.waived == False,
        )
    )
    total_fines = fines_result.scalar() or 0
    if total_fines >= MAX_FINE_BEFORE_BLOCK:
        raise HTTPException(
            status_code=400,
            detail={"code": "EXCESSIVE_FINES", "message": f"Outstanding fines of ${total_fines:.2f} exceed limit"}
        )

    # Check checkout limit
    checkouts_result = await session.execute(
        select(func.count()).where(
            CheckoutModel.patron_id == request.patron_id,
            CheckoutModel.status == "active",
        )
    )
    current_checkouts = checkouts_result.scalar() or 0
    if current_checkouts >= patron.checkout_limit:
        raise HTTPException(
            status_code=400,
            detail={"code": "CHECKOUT_LIMIT_REACHED", "message": f"Patron has {current_checkouts} items checked out (limit: {patron.checkout_limit})"}
        )

    # Verify instance exists and is available.
    # Prefer the local circulation DB instance record; fallback to catalog lookup
    # for legacy IDs not mirrored locally.
    local_instance_result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.id == request.instance_id)
    )
    local_instance = local_instance_result.scalar_one_or_none()
    instance_book_id = None

    if local_instance:
        instance_book_id = local_instance.book_id
        if local_instance.status != InstanceStatus.AVAILABLE.value:
            raise HTTPException(
                status_code=400,
                detail={"code": "ITEM_NOT_AVAILABLE", "message": f"Item is {local_instance.status}"}
            )
    else:
        try:
            # Fallback to catalog service for instances not mirrored in circulation DB.
            instance_id_parts = request.instance_id.split('-')
            if len(instance_id_parts) >= 3 and instance_id_parts[0] == "inst":
                book_num = instance_id_parts[1]
                book_id = f"book-{book_num}"

                await call_catalog(f"/books/{book_id}")
                instances = await call_catalog(f"/books/{book_id}/instances")
                instance = next((inst for inst in instances if inst["id"] == request.instance_id), None)

                if not instance:
                    raise HTTPException(status_code=404, detail="Item not found")

                if instance["status"] != InstanceStatus.AVAILABLE.value:
                    raise HTTPException(
                        status_code=400,
                        detail={"code": "ITEM_NOT_AVAILABLE", "message": f"Item is {instance['status']}"}
                    )
                instance_book_id = instance.get("book_id")
            else:
                raise HTTPException(status_code=404, detail="Item not found")

        except ServiceNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found in catalog")
        except ServiceUnavailableError:
            raise HTTPException(status_code=503, detail="Catalog service unavailable")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error verifying item availability: {str(e)}")

    # Get loan period based on patron category
    try:
        loan_days, _, _ = PATRON_LOAN_RULES[PatronCategory(patron.category)]
    except (KeyError, ValueError):
        loan_days = DEFAULT_LOAN_DAYS

    # Create checkout
    checkout_id = f"checkout-{uuid4().hex[:8]}"
    now = datetime.now(UTC)
    due_date = now + timedelta(days=loan_days)

    checkout = CheckoutModel(
        id=checkout_id,
        instance_id=request.instance_id,
        patron_id=request.patron_id,
        checked_out_at=now,
        due_date=due_date,
        status="active",
        renewals_used=0,
        max_renewals=DEFAULT_MAX_RENEWALS,
    )
    session.add(checkout)
    await session.commit()

    # Update local instance status first (used by circulation tests and local flows).
    if local_instance:
        local_instance.status = InstanceStatus.CHECKED_OUT.value
        await session.commit()

    # Update instance status in catalog service when available.
    try:
        await call_catalog(
            f"/instances/{request.instance_id}/status",
            method="PATCH",
            data={"status": InstanceStatus.CHECKED_OUT.value}
        )
    except Exception as e:
        # Log error but don't fail checkout - status can be fixed manually
        print(f"Warning: Failed to update instance status in catalog: {e}")

    # Get actual book title from catalog when we know the book_id.
    book_title = await get_book_title(session, instance_book_id or "")

    return CheckoutResponse(
        checkout=Checkout(
            id=checkout.id,
            instance_id=checkout.instance_id,
            patron_id=checkout.patron_id,
            checked_out_at=checkout.checked_out_at,
            due_date=checkout.due_date,
            status=CheckoutStatus.ACTIVE,
        ),
        book_title=book_title,
        renewals_remaining=DEFAULT_MAX_RENEWALS,
    )


@router.get("/checkouts/{checkout_id}")
async def get_checkout(
    checkout_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get checkout details."""
    result = await session.execute(
        select(CheckoutModel).where(CheckoutModel.id == checkout_id)
    )
    checkout = result.scalar_one_or_none()

    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout not found")

    return Checkout(
        id=checkout.id,
        instance_id=checkout.instance_id,
        patron_id=checkout.patron_id,
        checked_out_at=checkout.checked_out_at,
        due_date=checkout.due_date,
        returned_at=checkout.returned_at,
        status=CheckoutStatus(checkout.status),
    )


@router.get("/patrons/{patron_id}/checkouts", response_model=list[Checkout])
async def get_patron_checkouts(
    patron_id: str,
    status: str | None = Query(None, description="Filter by status: active, returned, overdue"),
    session: AsyncSession = Depends(get_session),
):
    """List patron's checkouts."""
    query = select(CheckoutModel).where(CheckoutModel.patron_id == patron_id)

    if status:
        query = query.where(CheckoutModel.status == status)

    result = await session.execute(query)
    checkouts = result.scalars().all()

    return [
        Checkout(
            id=c.id,
            instance_id=c.instance_id,
            patron_id=c.patron_id,
            checked_out_at=c.checked_out_at,
            due_date=c.due_date,
            returned_at=c.returned_at,
            status=CheckoutStatus(c.status),
        )
        for c in checkouts
    ]


@router.post("/checkouts/{checkout_id}/renew", response_model=RenewalResponse)
async def renew_checkout(
    checkout_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Renew a checkout."""
    result = await session.execute(
        select(CheckoutModel).where(CheckoutModel.id == checkout_id)
    )
    checkout = result.scalar_one_or_none()

    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout not found")

    if checkout.status != "active":
        raise HTTPException(
            status_code=400,
            detail={"code": "RENEWAL_NOT_ALLOWED", "message": f"Cannot renew {checkout.status} checkout"}
        )

    if checkout.renewals_used >= checkout.max_renewals:
        raise HTTPException(
            status_code=400,
            detail={"code": "MAX_RENEWALS_REACHED", "message": f"Maximum renewals ({checkout.max_renewals}) reached"}
        )

    # Get the book_id from the instance (proper extraction)
    instance_result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.id == checkout.instance_id)
    )
    instance = instance_result.scalar_one_or_none()

    if not instance:
        raise HTTPException(
            status_code=404,
            detail="Book instance not found"
        )

    # Check if there are holds waiting on this book
    holds_result = await session.execute(
        select(func.count()).where(
            HoldModel.book_id == instance.book_id,
            HoldModel.status == "pending",
        )
    )
    holds_waiting = holds_result.scalar() or 0
    if holds_waiting > 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "HOLDS_WAITING", "message": f"{holds_waiting} hold(s) waiting for this item"}
        )

    # Extend due date
    checkout.due_date = datetime.now(UTC) + timedelta(days=DEFAULT_LOAN_DAYS)
    checkout.renewals_used += 1
    session.add(checkout)
    await session.commit()

    return RenewalResponse(
        checkout=Checkout(
            id=checkout.id,
            instance_id=checkout.instance_id,
            patron_id=checkout.patron_id,
            checked_out_at=checkout.checked_out_at,
            due_date=checkout.due_date,
            status=CheckoutStatus(checkout.status),
        ),
        new_due_date=checkout.due_date,
        renewals_remaining=checkout.max_renewals - checkout.renewals_used,
    )


# =============================================================================
# Return Endpoints
# =============================================================================

@router.post("/returns", response_model=ReturnResponse)
async def return_item(
    request: ReturnRequest,
    session: AsyncSession = Depends(get_session),
):
    """Return an item."""
    # Verify instance exists
    instance_result = await session.execute(
        select(BookInstanceModel).where(BookInstanceModel.id == request.instance_id)
    )
    instance = instance_result.scalar_one_or_none()

    if not instance:
        raise HTTPException(status_code=404, detail="Item not found")

    # Find the active checkout for this instance
    result = await session.execute(
        select(CheckoutModel).where(
            CheckoutModel.instance_id == request.instance_id,
            CheckoutModel.status.in_(["active", "overdue"]),
        )
    )
    checkout = result.scalar_one_or_none()

    if not checkout:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_ACTIVE_CHECKOUT", "message": "No active checkout found for this item"}
        )

    now = datetime.now(UTC)

    # Calculate fines if overdue
    fines_incurred = Decimal("0.00")
    # Ensure due_date is timezone-aware for comparison
    due_date = checkout.due_date.replace(tzinfo=UTC) if checkout.due_date.tzinfo is None else checkout.due_date
    if due_date < now:
        days_overdue = (now - due_date).days
        fines_incurred = Decimal(str(days_overdue * FINE_RATE_PER_DAY))

        if fines_incurred > 0:
            fine = FineModel(
                id=f"fine-{uuid4().hex[:8]}",
                patron_id=checkout.patron_id,
                checkout_id=checkout.id,
                reason="overdue",
                amount=float(fines_incurred),
                description=f"{days_overdue} days overdue",
                created_at=now,
            )
            session.add(fine)

    # Update checkout
    checkout.returned_at = now
    checkout.status = "returned"
    session.add(checkout)

    # Check for holds and process queue
    next_hold_patron = await process_hold_queue(session, instance.book_id)

    # Update instance status
    if next_hold_patron:
        # Someone is waiting for this item - goes to hold shelf
        instance.status = InstanceStatus.HOLD_SHELF.value
        instance.location = "Hold Shelf"
    elif request.dropbox:
        # No holds, but returned via dropbox
        instance.status = InstanceStatus.DROPBOX.value
    else:
        # No holds, regular return - back to shelf
        instance.status = InstanceStatus.AVAILABLE.value
        instance.location = instance.call_number  # Return to shelf
    session.add(instance)

    await session.commit()

    return ReturnResponse(
        checkout_id=checkout.id,
        returned_at=now,
        dropbox=request.dropbox,
        fines_incurred=fines_incurred,
        next_hold_patron=next_hold_patron,
    )


# =============================================================================
# Hold Endpoints
# =============================================================================

@router.post("/holds", response_model=HoldResponse)
async def place_hold(
    request: HoldRequest,
    session: AsyncSession = Depends(get_session),
):
    """Place a hold on a book."""
    # Verify patron
    patron_result = await session.execute(
        select(PatronModel).where(PatronModel.id == request.patron_id)
    )
    patron = patron_result.scalar_one_or_none()

    if not patron:
        raise HTTPException(status_code=404, detail="Patron not found")

    # Check if patron is blocked
    if patron.blocked:
        raise HTTPException(
            status_code=400,
            detail={"code": "PATRON_BLOCKED", "message": patron.block_reason or "Patron is blocked"}
        )

    # Check hold limit
    holds_result = await session.execute(
        select(func.count()).where(
            HoldModel.patron_id == request.patron_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    current_holds = holds_result.scalar() or 0
    if current_holds >= patron.hold_limit:
        raise HTTPException(
            status_code=400,
            detail={"code": "HOLD_LIMIT_REACHED", "message": f"Patron has {current_holds} active holds (limit: {patron.hold_limit})"}
        )

    # Check for duplicate hold
    dup_result = await session.execute(
        select(func.count()).where(
            HoldModel.patron_id == request.patron_id,
            HoldModel.book_id == request.book_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    if (dup_result.scalar() or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail={"code": "HOLD_ALREADY_EXISTS", "message": "Patron already has an active hold on this book"}
        )

    # Get current queue position
    position_result = await session.execute(
        select(func.count()).where(
            HoldModel.book_id == request.book_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    position = (position_result.scalar() or 0) + 1

    # Create hold
    hold = HoldModel(
        id=f"hold-{uuid4().hex[:8]}",
        book_id=request.book_id,
        patron_id=request.patron_id,
        position=position,
        status="pending",
        created_at=datetime.now(UTC),
    )
    session.add(hold)
    await session.commit()

    # Get actual book title from catalog
    book_title = await get_book_title(session, request.book_id)

    return HoldResponse(
        hold=Hold(
            id=hold.id,
            book_id=hold.book_id,
            patron_id=hold.patron_id,
            position=hold.position,
            status=HoldStatus.PENDING,
            created_at=hold.created_at,
        ),
        book_title=book_title,
        position=position,
        estimated_wait=f"{position * 2} weeks" if position > 1 else "Available soon",
    )


@router.get("/holds/{hold_id}")
async def get_hold(
    hold_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Get hold details."""
    result = await session.execute(
        select(HoldModel).where(HoldModel.id == hold_id)
    )
    hold = result.scalar_one_or_none()

    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")

    return Hold(
        id=hold.id,
        book_id=hold.book_id,
        patron_id=hold.patron_id,
        position=hold.position,
        status=HoldStatus(hold.status),
        created_at=hold.created_at,
        notified_at=hold.notified_at,
        expires_at=hold.expires_at,
    )


@router.get("/patrons/{patron_id}/holds", response_model=list[Hold])
async def get_patron_holds(
    patron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List patron's holds."""
    result = await session.execute(
        select(HoldModel).where(
            HoldModel.patron_id == patron_id,
            HoldModel.status.in_(["pending", "ready"]),
        )
    )
    holds = result.scalars().all()

    return [
        Hold(
            id=h.id,
            book_id=h.book_id,
            patron_id=h.patron_id,
            position=h.position,
            status=HoldStatus(h.status),
            created_at=h.created_at,
            notified_at=h.notified_at,
            expires_at=h.expires_at,
        )
        for h in holds
    ]


@router.delete("/holds/{hold_id}")
async def cancel_hold(
    hold_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Cancel a hold."""
    result = await session.execute(
        select(HoldModel).where(HoldModel.id == hold_id)
    )
    hold = result.scalar_one_or_none()

    if not hold:
        raise HTTPException(status_code=404, detail="Hold not found")

    hold.status = "cancelled"
    session.add(hold)
    await session.commit()

    return {"message": "Hold cancelled", "hold_id": hold_id}


# =============================================================================
# Fine Endpoints
# =============================================================================

@router.get("/patrons/{patron_id}/fines", response_model=FineListResponse)
async def get_patron_fines(
    patron_id: str,
    session: AsyncSession = Depends(get_session),
):
    """List patron's fines."""
    result = await session.execute(
        select(FineModel).where(
            FineModel.patron_id == patron_id,
            FineModel.paid == False,
            FineModel.waived == False,
        )
    )
    fines = result.scalars().all()

    total_owed = sum(Decimal(str(f.amount)) for f in fines)

    return FineListResponse(
        patron_id=patron_id,
        total_owed=total_owed,
        fines=[
            Fine(
                id=f.id,
                patron_id=f.patron_id,
                checkout_id=f.checkout_id,
                reason=FineReason(f.reason),
                amount=Decimal(str(f.amount)),
                description=f.description,
                paid=f.paid,
                paid_at=f.paid_at,
                waived=f.waived,
                waived_reason=f.waived_reason,
                created_at=f.created_at,
            )
            for f in fines
        ],
    )


@router.post("/fines/{fine_id}/pay", response_model=FinePaymentResponse)
async def pay_fine(
    fine_id: str,
    request: FinePaymentRequest,
    session: AsyncSession = Depends(get_session),
):
    """Pay a fine."""
    result = await session.execute(
        select(FineModel).where(FineModel.id == fine_id)
    )
    fine = result.scalar_one_or_none()

    if not fine:
        raise HTTPException(status_code=404, detail="Fine not found")

    if fine.paid:
        raise HTTPException(status_code=400, detail="Fine already paid")

    # Reject partial payments — full amount required
    if request.amount < Decimal(str(fine.amount)):
        raise HTTPException(
            status_code=400,
            detail={"code": "PARTIAL_PAYMENT_NOT_ALLOWED", "message": f"Full payment of ${fine.amount:.2f} required, got ${request.amount:.2f}"}
        )

    fine.paid = True
    fine.paid_at = datetime.now(UTC)
    session.add(fine)
    await session.commit()

    return FinePaymentResponse(
        fine=Fine(
            id=fine.id,
            patron_id=fine.patron_id,
            checkout_id=fine.checkout_id,
            reason=FineReason(fine.reason),
            amount=Decimal(str(fine.amount)),
            description=fine.description,
            paid=fine.paid,
            paid_at=fine.paid_at,
            waived=fine.waived,
            waived_reason=fine.waived_reason,
            created_at=fine.created_at,
        ),
        amount_paid=request.amount,
        remaining_balance=Decimal("0.00"),
    )


# --- Admin: Eval Reset & Seed ---

_DATA_DIR = Path(__file__).resolve().parents[4] / "data"


@router.post("/admin/reset-and-seed")
async def admin_reset_and_seed(session: AsyncSession = Depends(get_session)):
    """Drop all circulation rows and re-seed patrons from JSON.

    Gated behind EVAL_MODE=true environment variable.
    """
    if not eval_mode_enabled():
        raise HTTPException(status_code=403, detail="EVAL_MODE is not enabled")

    # Delete in dependency order
    for model in (FineModel, HoldModel, CheckoutModel, BookInstanceModel, PatronModel):
        await session.execute(delete(model))
    await session.commit()

    records = 0

    # Seed patrons
    patrons_path = _DATA_DIR / "hanno_patrons.json"
    if patrons_path.exists():
        patrons = json.loads(patrons_path.read_text(encoding="utf-8"))
        for pd in patrons:
            session.add(PatronModel(
                id=pd["id"], barcode=pd.get("barcode"), name=pd["name"],
                email=pd["email"], phone=pd.get("phone"),
                category=pd.get("category", "adult"),
                checkout_limit=pd.get("checkout_limit", 10),
                hold_limit=pd.get("hold_limit", 10),
            ))
            records += 1
        await session.commit()

    _logger.info("Circulation admin reset-and-seed completed: %d records", records)
    return {"status": "seeded", "service": "circulation", "records": records}
