"""
Unit tests for StateManager class.

Tests verify that the StateManager correctly enforces transitions,
creates audit trails, and identifies side effects.
"""

import pytest
from datetime import datetime, UTC
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from shared.constants import ILLRequestStatus, InboundLoanStatus
from ill.state_machine import StateManager, InvalidTransitionError
from ill.models import ILLRequestModel, InboundLoanModel, ILLAuditTrail


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(test_engine):
    """Create a test database session."""
    async with AsyncSession(test_engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
async def outbound_request(session):
    """Create a test outbound ILL request."""
    request = ILLRequestModel(
        id="ill-req-test-001",
        book_id="book-001",
        book_title="Test Book",
        isbn="978-0-123456-78-9",
        author="Test Author",
        patron_id="patron-001",
        patron_reference="TEST-P-001",
        source_library="test-library",
        status=ILLRequestStatus.PENDING_APPROVAL.value,
        priority="normal",
        requested_at=datetime.now(UTC),
    )
    session.add(request)
    await session.commit()
    await session.refresh(request)
    return request


@pytest.fixture
async def inbound_loan(session):
    """Create a test inbound loan."""
    loan = InboundLoanModel(
        id="inbound-loan-test-001",
        instance_id="instance-001",
        book_id="book-001",
        requesting_library="test-library",
        patron_reference="EXTERNAL-P-001",
        status=InboundLoanStatus.PENDING_APPROVAL.value,
        requested_at=datetime.now(UTC),
        due_date=datetime.now(UTC),
        loan_period_days=28,
    )
    session.add(loan)
    await session.commit()
    await session.refresh(loan)
    return loan


class TestStateManagerOutbound:
    """Test StateManager for outbound ILL requests."""

    @pytest.mark.asyncio
    async def test_valid_outbound_transition_updates_status(
        self, session, outbound_request
    ):
        """Valid transition should update request status."""
        state_manager = StateManager(session)

        updated_request, side_effects = await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value,
            changed_by="librarian-001",
            change_reason="Approved for patron research"
        )

        assert updated_request.status == ILLRequestStatus.REQUESTED.value

    @pytest.mark.asyncio
    async def test_valid_outbound_transition_creates_audit_trail(
        self, session, outbound_request
    ):
        """Valid transition should create audit trail entry."""
        state_manager = StateManager(session)

        # Store ID before commit to avoid lazy load issues
        request_id = outbound_request.id

        await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value,
            changed_by="librarian-001",
            change_reason="Approved for patron research"
        )
        await session.commit()

        # Query audit trail
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_id == request_id
            )
        )
        audit_entries = result.all()

        assert len(audit_entries) == 1
        entry = audit_entries[0]
        assert entry.from_status == ILLRequestStatus.PENDING_APPROVAL.value
        assert entry.to_status == ILLRequestStatus.REQUESTED.value
        assert entry.changed_by == "librarian-001"
        assert entry.change_reason == "Approved for patron research"
        assert entry.request_type == "outbound"

    @pytest.mark.asyncio
    async def test_invalid_outbound_transition_raises_error(
        self, session, outbound_request
    ):
        """Invalid transition should raise InvalidTransitionError."""
        state_manager = StateManager(session)

        # Try to skip directly to RECEIVED (invalid)
        with pytest.raises(InvalidTransitionError) as exc_info:
            await state_manager.transition_outbound_request(
                outbound_request,
                ILLRequestStatus.RECEIVED.value,
                changed_by="librarian-001",
                change_reason="Invalid skip"
            )

        assert "Invalid transition" in str(exc_info.value)
        assert ILLRequestStatus.PENDING_APPROVAL.value in str(exc_info.value)
        assert ILLRequestStatus.RECEIVED.value in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_outbound_side_effects_returned(
        self, session, outbound_request
    ):
        """Transition with side effects should return them."""
        state_manager = StateManager(session)

        # Move to RECEIVED first
        outbound_request.status = ILLRequestStatus.RECEIVED.value

        # Now transition to IN_USE (has side effect)
        updated_request, side_effects = await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.IN_USE.value,
            changed_by="system",
            change_reason="Auto-checkout on receipt"
        )

        assert "create_circulation_checkout" in side_effects

    @pytest.mark.asyncio
    async def test_outbound_transition_without_metadata(
        self, session, outbound_request
    ):
        """Transition should work without changed_by or change_reason."""
        state_manager = StateManager(session)

        # Store ID before any operations
        request_id = outbound_request.id

        updated_request, side_effects = await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value
        )

        assert updated_request.status == ILLRequestStatus.REQUESTED.value

        # Audit trail should still be created
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_id == request_id
            )
        )
        audit_entries = result.all()
        assert len(audit_entries) == 1
        assert audit_entries[0].changed_by is None
        assert audit_entries[0].change_reason is None


class TestStateManagerInbound:
    """Test StateManager for inbound loans."""

    @pytest.mark.asyncio
    async def test_valid_inbound_transition_updates_status(
        self, session, inbound_loan
    ):
        """Valid transition should update loan status."""
        state_manager = StateManager(session)

        updated_loan, side_effects = await state_manager.transition_inbound_loan(
            inbound_loan,
            InboundLoanStatus.APPROVED.value,
            changed_by="librarian-002",
            change_reason="Partner library has good track record"
        )

        assert updated_loan.status == InboundLoanStatus.APPROVED.value

    @pytest.mark.asyncio
    async def test_valid_inbound_transition_creates_audit_trail(
        self, session, inbound_loan
    ):
        """Valid transition should create audit trail entry."""
        state_manager = StateManager(session)

        # Store ID before commit to avoid lazy load issues
        loan_id = inbound_loan.id

        await state_manager.transition_inbound_loan(
            inbound_loan,
            InboundLoanStatus.APPROVED.value,
            changed_by="librarian-002",
            change_reason="Partner library has good track record"
        )
        await session.commit()

        # Query audit trail
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.loan_id == loan_id
            )
        )
        audit_entries = result.all()

        assert len(audit_entries) == 1
        entry = audit_entries[0]
        assert entry.from_status == InboundLoanStatus.PENDING_APPROVAL.value
        assert entry.to_status == InboundLoanStatus.APPROVED.value
        assert entry.changed_by == "librarian-002"
        assert entry.change_reason == "Partner library has good track record"
        assert entry.request_type == "inbound"

    @pytest.mark.asyncio
    async def test_invalid_inbound_transition_raises_error(
        self, session, inbound_loan
    ):
        """Invalid transition should raise InvalidTransitionError."""
        state_manager = StateManager(session)

        # Try to skip directly to ACTIVE (invalid)
        with pytest.raises(InvalidTransitionError) as exc_info:
            await state_manager.transition_inbound_loan(
                inbound_loan,
                InboundLoanStatus.ACTIVE.value,
                changed_by="librarian-002",
                change_reason="Invalid skip"
            )

        assert "Invalid transition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_inbound_side_effects_returned(
        self, session, inbound_loan
    ):
        """Transition with side effects should return them."""
        state_manager = StateManager(session)

        # Approve (has side effect)
        updated_loan, side_effects = await state_manager.transition_inbound_loan(
            inbound_loan,
            InboundLoanStatus.APPROVED.value,
            changed_by="librarian-002",
            change_reason="Approved for lending"
        )

        assert "reserve_catalog_instance" in side_effects

    @pytest.mark.asyncio
    async def test_inbound_return_triggers_release(
        self, session, inbound_loan
    ):
        """ACTIVE -> RETURNED should trigger instance release."""
        state_manager = StateManager(session)

        # Move to ACTIVE first
        inbound_loan.status = InboundLoanStatus.ACTIVE.value

        # Now transition to RETURNED (has side effect)
        updated_loan, side_effects = await state_manager.transition_inbound_loan(
            inbound_loan,
            InboundLoanStatus.RETURNED.value,
            changed_by="system",
            change_reason="Item returned by borrowing library"
        )

        assert "release_catalog_instance" in side_effects


class TestStateManagerAuditTrail:
    """Test audit trail functionality."""

    @pytest.mark.asyncio
    async def test_multiple_transitions_create_multiple_audit_entries(
        self, session, outbound_request
    ):
        """Multiple transitions should create separate audit entries."""
        state_manager = StateManager(session)

        # Store ID before any operations
        request_id = outbound_request.id

        # First transition: PENDING_APPROVAL -> REQUESTED
        await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value,
            changed_by="librarian-001",
            change_reason="Initial approval"
        )
        await session.commit()
        # Refresh object after commit to reload it with current state
        await session.refresh(outbound_request)

        # Second transition: REQUESTED -> SHIPPED
        await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.SHIPPED.value,
            changed_by="system",
            change_reason="Shipped by lending library"
        )
        await session.commit()

        # Query audit trail
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_id == request_id
            ).order_by(ILLAuditTrail.changed_at)
        )
        audit_entries = result.all()

        assert len(audit_entries) == 2

        # First entry
        assert audit_entries[0].from_status == ILLRequestStatus.PENDING_APPROVAL.value
        assert audit_entries[0].to_status == ILLRequestStatus.REQUESTED.value
        assert audit_entries[0].changed_by == "librarian-001"

        # Second entry
        assert audit_entries[1].from_status == ILLRequestStatus.REQUESTED.value
        assert audit_entries[1].to_status == ILLRequestStatus.SHIPPED.value
        assert audit_entries[1].changed_by == "system"

    @pytest.mark.asyncio
    async def test_audit_trail_timestamps_are_recorded(
        self, session, outbound_request
    ):
        """Audit trail timestamps should be recorded."""
        state_manager = StateManager(session)

        # Store ID before commit
        request_id = outbound_request.id

        await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value,
            changed_by="librarian-001"
        )
        await session.commit()
        # Refresh object after commit
        await session.refresh(outbound_request)

        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_id == request_id
            )
        )
        entry = result.one()

        # Check that timestamp exists
        # Note: SQLite doesn't preserve timezone info, but timestamps are created with UTC
        assert entry.changed_at is not None
        assert isinstance(entry.changed_at, datetime)

    @pytest.mark.asyncio
    async def test_audit_trail_distinguishes_request_types(
        self, session, outbound_request, inbound_loan
    ):
        """Audit trail should distinguish between outbound and inbound."""
        state_manager = StateManager(session)

        # Store IDs before any operations
        request_id = outbound_request.id
        loan_id = inbound_loan.id

        # Create both types
        await state_manager.transition_outbound_request(
            outbound_request,
            ILLRequestStatus.REQUESTED.value,
            changed_by="librarian-001"
        )

        await state_manager.transition_inbound_loan(
            inbound_loan,
            InboundLoanStatus.APPROVED.value,
            changed_by="librarian-002"
        )
        await session.commit()
        # Refresh objects after commit
        await session.refresh(outbound_request)
        await session.refresh(inbound_loan)

        # Query outbound audit trail
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_type == "outbound"
            )
        )
        outbound_entries = result.all()
        assert len(outbound_entries) == 1
        assert outbound_entries[0].request_id == request_id
        assert outbound_entries[0].loan_id is None

        # Query inbound audit trail
        result = await session.exec(
            select(ILLAuditTrail).where(
                ILLAuditTrail.request_type == "inbound"
            )
        )
        inbound_entries = result.all()
        assert len(inbound_entries) == 1
        assert inbound_entries[0].loan_id == loan_id
        assert inbound_entries[0].request_id is None
