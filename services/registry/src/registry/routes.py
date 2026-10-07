"""API routes for the registry service."""

import logging
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from registry.db import get_session
from registry.models import PartnerLibraryModel, LibraryMetricsModel
from shared.eval.admin_seed import eval_mode_enabled

_logger = logging.getLogger(__name__)
from registry.a2a_relay import relay_store
from registry.schemas import (
    HealthResponse,
    PartnerLibraryCreate,
    PartnerLibraryUpdate,
    PartnerLibraryResponse,
    LibrarySelectionRequest,
    LibrarySelectionResponse,
)
from shared.a2a.schemas import (
    A2AAckRequest,
    A2AAckResponse,
    A2AInboxResponse,
    A2ASendRequest,
    A2ASendResponse,
)

router = APIRouter()
LOCAL_LIBRARY_CODE = "hanno-memorial"


async def _library_exists_or_local(code: str, session: AsyncSession) -> bool:
    """Validate library code against registry or local code."""
    if code == LOCAL_LIBRARY_CODE:
        return True
    result = await session.execute(
        select(PartnerLibraryModel).where(
            PartnerLibraryModel.code == code,
            PartnerLibraryModel.status == "active",
        )
    )
    return result.scalar_one_or_none() is not None


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="registry",
        version="0.1.0",
        library="Hanno Memorial Library"
    )


# =============================================================================
# A2A Relay (MVP)
# =============================================================================


@router.post("/a2a/message/send", response_model=A2ASendResponse)
async def send_a2a_message(
    request: A2ASendRequest,
    session: AsyncSession = Depends(get_session),
    x_library_code: str | None = Header(default=None),
):
    """Relay one A2A message to the destination library inbox."""
    message = request.message
    if x_library_code != message.from_library:
        raise HTTPException(status_code=403, detail="Sender header mismatch")

    sender_valid = await _library_exists_or_local(message.from_library, session)
    receiver_valid = await _library_exists_or_local(message.to_library, session)
    if not sender_valid or not receiver_valid:
        raise HTTPException(status_code=400, detail="Invalid sender or receiver library")

    is_new = relay_store.send(message)
    return A2ASendResponse(
        accepted=True,
        message_id=message.id,
        queued_for=message.to_library,
        status="queued" if is_new else "duplicate",
    )


@router.get("/a2a/messages/{library_code}", response_model=A2AInboxResponse)
async def get_a2a_inbox(
    library_code: str,
    include_acknowledged: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    x_library_code: str | None = Header(default=None),
):
    """Get queued A2A messages for one library."""
    if x_library_code != library_code:
        raise HTTPException(status_code=403, detail="Inbox access denied")

    valid = await _library_exists_or_local(library_code, session)
    if not valid:
        raise HTTPException(status_code=404, detail="Library not found")

    messages = relay_store.inbox(
        library_code=library_code,
        include_acknowledged=include_acknowledged,
        limit=limit,
    )
    return A2AInboxResponse(
        library_code=library_code,
        total=len(messages),
        messages=messages,
    )


@router.post("/a2a/messages/{message_id}/ack", response_model=A2AAckResponse)
async def acknowledge_a2a_message(
    message_id: str,
    request: A2AAckRequest,
    session: AsyncSession = Depends(get_session),
    x_library_code: str | None = Header(default=None),
):
    """Acknowledge one inbox message."""
    if x_library_code != request.library_code:
        raise HTTPException(status_code=403, detail="Ack access denied")

    valid = await _library_exists_or_local(request.library_code, session)
    if not valid:
        raise HTTPException(status_code=404, detail="Library not found")

    ok = relay_store.acknowledge(request.library_code, message_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")

    return A2AAckResponse(
        acknowledged=True,
        message_id=message_id,
        library_code=request.library_code,
    )


@router.get("/libraries", response_model=list[PartnerLibraryResponse])
async def list_libraries(
    status: str | None = Query(None, description="Filter by status (active, suspended, inactive)"),
    lending_enabled: bool | None = Query(None, description="Filter by lending enabled"),
    borrowing_enabled: bool | None = Query(None, description="Filter by borrowing enabled"),
    session: AsyncSession = Depends(get_session)
):
    """List all partner libraries with optional filters."""
    # Build base query
    query = select(PartnerLibraryModel)

    # Apply filters
    if status:
        query = query.where(PartnerLibraryModel.status == status)
    if lending_enabled is not None:
        query = query.where(PartnerLibraryModel.lending_enabled == lending_enabled)
    if borrowing_enabled is not None:
        query = query.where(PartnerLibraryModel.borrowing_enabled == borrowing_enabled)

    # Execute query
    result = await session.execute(query)
    libraries = result.scalars().all()

    # Load metrics for each library
    response_libraries = []
    for lib in libraries:
        # Load metrics
        metrics_result = await session.execute(
            select(LibraryMetricsModel).where(LibraryMetricsModel.library_code == lib.code)
        )
        metrics = metrics_result.scalar_one_or_none()

        response_libraries.append(
            PartnerLibraryResponse(
                code=lib.code,
                name=lib.name,
                display_name=lib.display_name,
                contact_name=lib.contact_name,
                contact_email=lib.contact_email,
                contact_phone=lib.contact_phone,
                address=lib.address,
                catalog_url=lib.catalog_url,
                status=lib.status,
                member_since=lib.member_since,
                lending_enabled=lib.lending_enabled,
                borrowing_enabled=lib.borrowing_enabled,
                loan_period_days=lib.loan_period_days,
                auto_approve_requests=lib.auto_approve_requests,
                specializations=lib.specializations,
                notes=lib.notes,
                metrics=metrics,
            )
        )

    return response_libraries


@router.get("/libraries/{code}", response_model=PartnerLibraryResponse)
async def get_library(
    code: str,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed information about a specific library."""
    # Load library
    result = await session.execute(
        select(PartnerLibraryModel).where(PartnerLibraryModel.code == code)
    )
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    # Load metrics
    metrics_result = await session.execute(
        select(LibraryMetricsModel).where(LibraryMetricsModel.library_code == code)
    )
    metrics = metrics_result.scalar_one_or_none()

    return PartnerLibraryResponse(
        code=library.code,
        name=library.name,
        display_name=library.display_name,
        contact_name=library.contact_name,
        contact_email=library.contact_email,
        contact_phone=library.contact_phone,
        address=library.address,
        catalog_url=library.catalog_url,
        status=library.status,
        member_since=library.member_since,
        lending_enabled=library.lending_enabled,
        borrowing_enabled=library.borrowing_enabled,
        loan_period_days=library.loan_period_days,
        auto_approve_requests=library.auto_approve_requests,
        specializations=library.specializations,
        notes=library.notes,
        metrics=metrics,
    )


@router.post("/libraries", response_model=PartnerLibraryResponse, status_code=201)
async def create_library(
    library: PartnerLibraryCreate,
    session: AsyncSession = Depends(get_session)
):
    """Add a new partner library to the registry."""
    # Check if library code already exists
    existing = await session.execute(
        select(PartnerLibraryModel).where(PartnerLibraryModel.code == library.code)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Library code already exists")

    # Create library
    now = datetime.now(UTC)
    new_library = PartnerLibraryModel(
        code=library.code,
        name=library.name,
        display_name=library.display_name,
        contact_name=library.contact_name,
        contact_email=library.contact_email,
        contact_phone=library.contact_phone,
        address=library.address,
        catalog_url=library.catalog_url,
        member_since=now,
        lending_enabled=library.lending_enabled,
        borrowing_enabled=library.borrowing_enabled,
        loan_period_days=library.loan_period_days,
        auto_approve_requests=library.auto_approve_requests,
        specializations=library.specializations,
        notes=library.notes,
    )
    session.add(new_library)

    # Create default metrics
    metrics = LibraryMetricsModel(
        library_code=library.code,
        last_updated=now,
    )
    session.add(metrics)

    await session.commit()
    await session.refresh(new_library)
    await session.refresh(metrics)

    return PartnerLibraryResponse(
        code=new_library.code,
        name=new_library.name,
        display_name=new_library.display_name,
        contact_name=new_library.contact_name,
        contact_email=new_library.contact_email,
        contact_phone=new_library.contact_phone,
        address=new_library.address,
        catalog_url=new_library.catalog_url,
        status=new_library.status,
        member_since=new_library.member_since,
        lending_enabled=new_library.lending_enabled,
        borrowing_enabled=new_library.borrowing_enabled,
        loan_period_days=new_library.loan_period_days,
        auto_approve_requests=new_library.auto_approve_requests,
        specializations=new_library.specializations,
        notes=new_library.notes,
        metrics=metrics,
    )


@router.patch("/libraries/{code}", response_model=PartnerLibraryResponse)
async def update_library(
    code: str,
    updates: PartnerLibraryUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update partner library information."""
    # Load library
    result = await session.execute(
        select(PartnerLibraryModel).where(PartnerLibraryModel.code == code)
    )
    library = result.scalar_one_or_none()

    if not library:
        raise HTTPException(status_code=404, detail="Library not found")

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(library, key, value)

    await session.commit()
    await session.refresh(library)

    # Load metrics
    metrics_result = await session.execute(
        select(LibraryMetricsModel).where(LibraryMetricsModel.library_code == code)
    )
    metrics = metrics_result.scalar_one_or_none()

    return PartnerLibraryResponse(
        code=library.code,
        name=library.name,
        display_name=library.display_name,
        contact_name=library.contact_name,
        contact_email=library.contact_email,
        contact_phone=library.contact_phone,
        address=library.address,
        catalog_url=library.catalog_url,
        status=library.status,
        member_since=library.member_since,
        lending_enabled=library.lending_enabled,
        borrowing_enabled=library.borrowing_enabled,
        loan_period_days=library.loan_period_days,
        auto_approve_requests=library.auto_approve_requests,
        specializations=library.specializations,
        notes=library.notes,
        metrics=metrics,
    )


@router.post("/libraries/select-best", response_model=LibrarySelectionResponse)
async def select_best_library(
    request: LibrarySelectionRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Select the best partner library for an ILL request.

    Selection criteria:
    1. Library specializations match book genre
    2. High fulfillment rate (>80%)
    3. Fast response time (<24 hours)
    4. Active status and lending enabled
    5. No excessive overdue items
    """
    # Query active libraries with lending enabled
    result = await session.execute(
        select(PartnerLibraryModel).where(
            PartnerLibraryModel.status == "active",
            PartnerLibraryModel.lending_enabled == True
        )
    )
    libraries = result.scalars().all()

    if not libraries:
        raise HTTPException(status_code=404, detail="No active lending libraries available")

    # Load metrics and score each library
    best_library = None
    best_score = -1
    best_reasoning = ""

    for lib in libraries:
        # Load metrics
        metrics_result = await session.execute(
            select(LibraryMetricsModel).where(LibraryMetricsModel.library_code == lib.code)
        )
        metrics = metrics_result.scalar_one_or_none()

        score = 0
        reasons = []

        # Check specialization match
        if request.genre and lib.specializations:
            if any(spec.lower() in request.genre.lower() or request.genre.lower() in spec.lower()
                   for spec in lib.specializations):
                score += 30
                reasons.append(f"Specializes in {request.genre}")

        # Check fulfillment rate
        if metrics and metrics.fulfillment_rate:
            if metrics.fulfillment_rate >= 0.9:
                score += 25
                reasons.append(f"{metrics.fulfillment_rate*100:.0f}% fulfillment rate")
            elif metrics.fulfillment_rate >= 0.8:
                score += 15

        # Check response time
        if metrics and metrics.avg_response_time_hours:
            if metrics.avg_response_time_hours <= 24:
                score += 20
                reasons.append(f"{metrics.avg_response_time_hours:.1f}hr avg response")
            elif metrics.avg_response_time_hours <= 48:
                score += 10

        # Check reliability (on-time returns)
        if metrics and metrics.on_time_return_rate:
            if metrics.on_time_return_rate >= 0.95:
                score += 15
                reasons.append("Excellent return record")
            elif metrics.on_time_return_rate >= 0.85:
                score += 10

        # Penalize for overdue items
        if metrics and metrics.overdue_items_count > 5:
            score -= 10
            reasons.append(f"Warning: {metrics.overdue_items_count} overdue items")

        if score > best_score:
            best_score = score
            best_library = lib
            best_reasoning = "; ".join(reasons) if reasons else "Active library with lending enabled"

            # Add metrics data
            if metrics:
                estimated_response = metrics.avg_response_time_hours
                fulfillment = metrics.fulfillment_rate
            else:
                estimated_response = None
                fulfillment = None

    if not best_library:
        raise HTTPException(status_code=404, detail="No suitable library found")

    # Determine confidence level
    if best_score >= 50:
        confidence = "high"
    elif best_score >= 30:
        confidence = "medium"
    else:
        confidence = "low"

    return LibrarySelectionResponse(
        library_code=best_library.code,
        library_name=best_library.display_name,
        confidence=confidence,
        reasoning=best_reasoning,
        estimated_response_hours=estimated_response,
        fulfillment_rate=fulfillment,
    )


# --- Admin: Eval Reset & Seed ---

_PARTNER_LIBRARIES = [
    {
        "code": "mastodon-institute",
        "name": "mastodon-institute",
        "display_name": "Mastodon Institute Library",
        "status": "active",
        "member_since": datetime(2020, 1, 1, tzinfo=UTC),
        "lending_enabled": True,
        "borrowing_enabled": True,
        "loan_period_days": 28,
        "auto_approve_requests": False,
        "max_concurrent_loans": 10,
        "catalog_url": "http://localhost:8011",
        "specializations": ["paleontology", "ancient-history", "geology"],
    },
    {
        "code": "mammoth-valley",
        "name": "mammoth-valley",
        "display_name": "Mammoth Valley Public Library",
        "status": "active",
        "member_since": datetime(2020, 1, 1, tzinfo=UTC),
        "lending_enabled": True,
        "borrowing_enabled": True,
        "loan_period_days": 28,
        "auto_approve_requests": False,
        "max_concurrent_loans": 15,
        "catalog_url": "http://localhost:8012",
        "specializations": ["local-history", "genealogy", "fiction"],
    },
    {
        "code": "ivory-university",
        "name": "ivory-university",
        "display_name": "Ivory University Research Library",
        "status": "active",
        "member_since": datetime(2020, 1, 1, tzinfo=UTC),
        "lending_enabled": True,
        "borrowing_enabled": True,
        "loan_period_days": 21,
        "auto_approve_requests": True,
        "max_concurrent_loans": 20,
        "catalog_url": "http://localhost:8013",
        "specializations": ["philosophy", "ethics", "logic"],
    },
    {
        "code": "tusk-conservatory",
        "name": "tusk-conservatory",
        "display_name": "Tusk Conservatory Archives",
        "status": "active",
        "member_since": datetime(2020, 1, 1, tzinfo=UTC),
        "lending_enabled": True,
        "borrowing_enabled": True,
        "loan_period_days": 14,
        "auto_approve_requests": False,
        "max_concurrent_loans": 5,
        "catalog_url": "http://localhost:8014",
        "specializations": ["music", "performing-arts", "conservation"],
    },
]


@router.post("/admin/reset-and-seed")
async def admin_reset_and_seed(session: AsyncSession = Depends(get_session)):
    """Drop all registry rows and re-seed partner libraries.

    Gated behind EVAL_MODE=true environment variable.
    """
    if not eval_mode_enabled():
        raise HTTPException(status_code=403, detail="EVAL_MODE is not enabled")

    await session.execute(delete(LibraryMetricsModel))
    await session.execute(delete(PartnerLibraryModel))
    await session.commit()

    records = 0
    for lib in _PARTNER_LIBRARIES:
        session.add(PartnerLibraryModel(**lib))
        session.add(LibraryMetricsModel(
            library_code=lib["code"],
            last_updated=datetime.now(UTC),
        ))
        records += 2
    await session.commit()

    _logger.info("Registry admin reset-and-seed completed: %d records", records)
    return {"status": "seeded", "service": "registry", "records": records}
