"""State machine for ILL workflow management."""

from datetime import datetime, UTC
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from ill.models import ILLRequestModel, InboundLoanModel, ILLAuditTrail
from ill.state_transitions import (
    is_valid_outbound_transition,
    is_valid_inbound_transition,
    get_outbound_side_effects,
    get_inbound_side_effects,
)


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class StateManager:
    """Manages state transitions for ILL requests and loans with audit trail."""

    def __init__(self, session: AsyncSession):
        """Initialize state manager with database session."""
        self.session = session

    async def transition_outbound_request(
        self,
        request: ILLRequestModel,
        to_status: str,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> tuple[ILLRequestModel, list[str]]:
        """
        Transition an outbound ILL request to a new status.

        Args:
            request: The ILL request to transition
            to_status: The target status
            changed_by: ID of user/agent making the change
            change_reason: Reason for the transition

        Returns:
            Tuple of (updated request, list of side effects to execute)

        Raises:
            InvalidTransitionError: If the transition is not allowed
        """
        from_status = request.status

        # Validate transition
        if not is_valid_outbound_transition(from_status, to_status):
            raise InvalidTransitionError(
                f"Invalid transition from '{from_status}' to '{to_status}' "
                f"for outbound request {request.id}"
            )

        # Get side effects for this transition
        side_effects = get_outbound_side_effects(from_status, to_status)

        # Update request status
        request.status = to_status

        # Create audit trail entry
        audit_entry = ILLAuditTrail(
            id=f"audit-{uuid4().hex[:12]}",
            request_id=request.id,
            loan_id=None,
            request_type="outbound",
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            change_reason=change_reason,
            changed_at=datetime.now(UTC),
        )

        self.session.add(audit_entry)

        return request, side_effects

    async def transition_inbound_loan(
        self,
        loan: InboundLoanModel,
        to_status: str,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> tuple[InboundLoanModel, list[str]]:
        """
        Transition an inbound loan to a new status.

        Args:
            loan: The inbound loan to transition
            to_status: The target status
            changed_by: ID of user/agent making the change
            change_reason: Reason for the transition

        Returns:
            Tuple of (updated loan, list of side effects to execute)

        Raises:
            InvalidTransitionError: If the transition is not allowed
        """
        from_status = loan.status

        # Validate transition
        if not is_valid_inbound_transition(from_status, to_status):
            raise InvalidTransitionError(
                f"Invalid transition from '{from_status}' to '{to_status}' "
                f"for inbound loan {loan.id}"
            )

        # Get side effects for this transition
        side_effects = get_inbound_side_effects(from_status, to_status)

        # Update loan status
        loan.status = to_status

        # Create audit trail entry
        audit_entry = ILLAuditTrail(
            id=f"audit-{uuid4().hex[:12]}",
            request_id=None,
            loan_id=loan.id,
            request_type="inbound",
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            change_reason=change_reason,
            changed_at=datetime.now(UTC),
        )

        self.session.add(audit_entry)

        return loan, side_effects

    async def get_request_audit_trail(self, request_id: str) -> list[ILLAuditTrail]:
        """Get audit trail for an outbound request."""
        from sqlalchemy import select

        result = await self.session.execute(
            select(ILLAuditTrail)
            .where(ILLAuditTrail.request_id == request_id)
            .order_by(ILLAuditTrail.changed_at.asc())
        )
        return list(result.scalars().all())

    async def get_loan_audit_trail(self, loan_id: str) -> list[ILLAuditTrail]:
        """Get audit trail for an inbound loan."""
        from sqlalchemy import select

        result = await self.session.execute(
            select(ILLAuditTrail)
            .where(ILLAuditTrail.loan_id == loan_id)
            .order_by(ILLAuditTrail.changed_at.asc())
        )
        return list(result.scalars().all())
