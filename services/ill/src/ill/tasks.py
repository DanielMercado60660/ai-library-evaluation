"""Celery tasks for ILL service.

Background tasks for long-running ILL operations:
- Auto-checkout creation when ILL items received
- Catalog instance status updates (reserve/release)
- Partner library notifications
- Overdue item checking
"""

import asyncio
import os
from datetime import datetime, UTC
from celery import Task
from celery.utils.log import get_task_logger
from sqlmodel import Session, select, create_engine
from shared.http_client import call_circulation, call_catalog, ServiceNotFoundError, ServiceUnavailableError
from shared.constants import ILLRequestStatus, InboundLoanStatus
from ill.models import ILLRequestModel, InboundLoanModel
from ill.celery_app import app
from ill.a2a_client import send_a2a_message
from shared.a2a.schemas import A2AMessageType

logger = get_task_logger(__name__)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db/ill.db")
engine = create_engine(DATABASE_URL)


class ILLTask(Task):
    """Base task class with error handling and retries."""

    autoretry_for = (ServiceUnavailableError, ConnectionError)
    retry_kwargs = {"max_retries": 3}
    retry_backoff = True  # Exponential backoff
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True  # Add randomness to avoid thundering herd


# =============================================================================
# Outbound ILL Tasks (Borrowing)
# =============================================================================

@app.task(base=ILLTask, bind=True)
def create_circulation_checkout(self, request_id: str) -> dict:
    """
    Create a circulation checkout when an ILL item is received.

    This task is triggered when an ILL request transitions from RECEIVED to IN_USE.
    It calls the circulation service to create a checkout for the patron.

    Args:
        request_id: ID of the ILL request

    Returns:
        Dict with checkout details or error info
    """
    logger.info(f"Creating checkout for ILL request {request_id}")

    try:
        with Session(engine) as session:
            # Get ILL request
            result = session.execute(
                select(ILLRequestModel).where(ILLRequestModel.id == request_id)
            )
            ill_request = result.scalar_one_or_none()

            if not ill_request:
                logger.error(f"ILL request {request_id} not found")
                return {"success": False, "error": "Request not found"}

            # Verify request is in correct state
            if ill_request.status != ILLRequestStatus.IN_USE.value:
                logger.warning(f"ILL request {request_id} not in IN_USE state (current: {ill_request.status})")
                return {"success": False, "error": f"Invalid state: {ill_request.status}"}

            # Create checkout via circulation service
            checkout_data = {
                "patron_id": ill_request.patron_id,
                "instance_id": f"ill-{request_id}",  # Virtual instance for ILL item
                "due_date": ill_request.due_date.isoformat() if ill_request.due_date else None,
                "notes": f"ILL item from {ill_request.source_library}",
            }

            try:
                checkout_response = call_circulation("/checkouts", method="POST", json=checkout_data)
                logger.info(f"Created checkout {checkout_response.get('id')} for ILL request {request_id}")
                return {"success": True, "checkout_id": checkout_response.get("id")}

            except ServiceNotFoundError:
                # Patron might be blocked or invalid
                logger.error(f"Failed to create checkout for request {request_id}: patron not found or blocked")
                return {"success": False, "error": "Patron not found or blocked"}

    except Exception as e:
        logger.exception(f"Unexpected error creating checkout for request {request_id}: {e}")
        raise self.retry(exc=e, countdown=60)


# =============================================================================
# Inbound Loan Tasks (Lending)
# =============================================================================

@app.task(base=ILLTask, bind=True)
def update_catalog_status(self, loan_id: str, action: str) -> dict:
    """
    Update catalog instance status for inbound loans.

    Actions:
    - "reserve": Mark instance as on_loan when loan approved
    - "release": Mark instance as available when loan returned

    Args:
        loan_id: ID of the inbound loan
        action: "reserve" or "release"

    Returns:
        Dict with update status
    """
    logger.info(f"Updating catalog status for loan {loan_id}, action: {action}")

    if action not in ["reserve", "release"]:
        logger.error(f"Invalid action: {action}")
        return {"success": False, "error": "Invalid action"}

    try:
        with Session(engine) as session:
            # Get inbound loan
            result = session.execute(
                select(InboundLoanModel).where(InboundLoanModel.id == loan_id)
            )
            inbound_loan = result.scalar_one_or_none()

            if not inbound_loan:
                logger.error(f"Inbound loan {loan_id} not found")
                return {"success": False, "error": "Loan not found"}

            # Determine new status based on action
            if action == "reserve":
                new_status = "on_loan"
                expected_loan_status = InboundLoanStatus.APPROVED.value
            else:  # release
                new_status = "available"
                expected_loan_status = InboundLoanStatus.RETURNED.value

            # Verify loan is in expected state
            if inbound_loan.status != expected_loan_status:
                logger.warning(
                    f"Loan {loan_id} not in expected state for {action} "
                    f"(current: {inbound_loan.status}, expected: {expected_loan_status})"
                )
                # Continue anyway - might be a retry after state changed

            # Update instance status via catalog service
            update_data = {"status": new_status}

            try:
                catalog_response = call_catalog(
                    f"/instances/{inbound_loan.instance_id}",
                    method="PATCH",
                    json=update_data
                )
                logger.info(
                    f"Updated instance {inbound_loan.instance_id} to {new_status} "
                    f"for loan {loan_id}"
                )
                return {"success": True, "instance_id": inbound_loan.instance_id, "status": new_status}

            except ServiceNotFoundError:
                logger.error(f"Instance {inbound_loan.instance_id} not found in catalog")
                return {"success": False, "error": "Instance not found"}

    except Exception as e:
        logger.exception(f"Unexpected error updating catalog status for loan {loan_id}: {e}")
        raise self.retry(exc=e, countdown=60)


# =============================================================================
# Notification Tasks
# =============================================================================

@app.task(base=ILLTask, bind=True)
def notify_partner_library(self, library_code: str, message_type: str, data: dict) -> dict:
    """
    Send notification to a partner library.

    Placeholder for A2A protocol implementation (Phase 2).

    Args:
        library_code: Partner library code
        message_type: Type of notification (e.g., "request_sent", "item_returned")
        data: Notification data

    Returns:
        Dict with notification status
    """
    logger.info(f"Sending {message_type} notification to {library_code}")

    logger.info("Notification data: %s", data)
    try:
        envelope_type = A2AMessageType(message_type)
    except ValueError:
        envelope_type = A2AMessageType.ERROR

    try:
        response = asyncio.run(
            send_a2a_message(
                to_library=library_code,
                message_type=envelope_type,
                correlation_id=data.get("request_id"),
                payload=data,
            )
        )
        return {"success": True, "message": "Notification sent", "relay": response}
    except Exception as exc:
        logger.exception("A2A partner notification failed: %s", exc)
        return {"success": False, "error": str(exc)}


# =============================================================================
# Periodic Tasks
# =============================================================================

@app.task(base=ILLTask, bind=True)
def check_overdue_ill_items(self) -> dict:
    """
    Check for overdue ILL items and send notifications.

    This task should be scheduled to run daily via Celery Beat.

    Returns:
        Dict with count of overdue items found
    """
    logger.info("Checking for overdue ILL items")

    try:
        with Session(engine) as session:
            now = datetime.now(UTC)

            # Find overdue outbound requests
            result = session.execute(
                select(ILLRequestModel).where(
                    ILLRequestModel.status == ILLRequestStatus.IN_USE,
                    ILLRequestModel.due_date < now
                )
            )
            overdue_requests = result.scalars().all()

            logger.info(f"Found {len(overdue_requests)} overdue ILL items")

            # TODO: Send notifications for overdue items
            # For now, just log them
            for request in overdue_requests:
                logger.warning(
                    f"ILL request {request.id} is overdue "
                    f"(due: {request.due_date}, patron: {request.patron_id})"
                )

            return {"success": True, "overdue_count": len(overdue_requests)}

    except Exception as e:
        logger.exception(f"Error checking overdue items: {e}")
        raise self.retry(exc=e, countdown=300)
