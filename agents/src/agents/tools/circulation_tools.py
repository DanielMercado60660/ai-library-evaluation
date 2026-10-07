"""Tools for interacting with the circulation service."""

import httpx
from typing import Optional

from agents.config import CIRCULATION_URL
from agents.session.active_patron_context import get_active_patron_context
from agents.utils.resilience import with_retry
from shared.auth import SERVICE_TOKEN_HEADER, get_service_token
from shared.eval.runtime_trace import begin_tool_call, end_tool_call


def _auth_headers() -> dict[str, str]:
    return {SERVICE_TOKEN_HEADER: get_service_token()}


def _policy_error(message: str) -> dict:
    """Return a consistent policy/error payload."""
    return {"error": message}


def _resolve_active_patron_id() -> str | None:
    """Resolve active patron ID from request-scoped context."""
    context = get_active_patron_context()
    return context.patron_id if context else None


def _enforce_active_patron_match(patron_id: str) -> dict | None:
    """Block cross-patron account actions when active context is bound."""
    active_patron_id = _resolve_active_patron_id()
    if active_patron_id and patron_id != active_patron_id:
        return _policy_error(
            "Account actions are bound to the active profile. "
            "Switch active patron profile and retry."
        )
    return None


@with_retry(max_attempts=3)
async def get_patron(patron_id: str) -> dict:
    """
    Get patron details by ID.

    Args:
        patron_id: The unique identifier of the patron

    Returns:
        Dictionary containing patron information
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="get_patron",
        input_payload={"patron_id": patron_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CIRCULATION_URL}/patrons/{patron_id}",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "Patron not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="get_patron",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="get_patron",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="get_patron",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def get_patron_summary(patron_id: str) -> dict:
    """
    Get comprehensive summary of patron's account including checkouts, holds, and fines.

    Args:
        patron_id: The unique identifier of the patron

    Returns:
        Dictionary containing:
        - patron: Patron details
        - checkouts: List of current checkouts
        - holds: List of active holds
        - fines: List of unpaid fines
        - total_fines: Total amount owed
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="get_patron_summary",
        input_payload={"patron_id": patron_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CIRCULATION_URL}/patrons/{patron_id}/summary",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "Patron not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="get_patron_summary",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="get_patron_summary",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="get_patron_summary",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def checkout_item(instance_id: str, patron_id: str) -> dict:
    """
    Check out a book instance to a patron.

    Args:
        instance_id: The ID of the book instance to check out
        patron_id: The ID of the patron checking out

    Returns:
        Dictionary containing checkout confirmation or error
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="checkout_item",
        input_payload={"instance_id": instance_id, "patron_id": patron_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CIRCULATION_URL}/checkouts",
                json={"instance_id": instance_id, "patron_id": patron_id},
                headers=_auth_headers(),
            )
            if response.status_code == 400:
                payload = response.json()
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="checkout_item",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload={"status_code": 400, "result": payload},
                )
                return payload
            if response.status_code == 404:
                payload = {"error": "Item or patron not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="checkout_item",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="checkout_item",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="checkout_item",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def renew_checkout(checkout_id: str) -> dict:
    """
    Renew an existing checkout.

    Args:
        checkout_id: The ID of the checkout to renew

    Returns:
        Dictionary containing renewal confirmation or error
    """
    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="renew_checkout",
        input_payload={"checkout_id": checkout_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CIRCULATION_URL}/checkouts/{checkout_id}/renew",
                headers=_auth_headers(),
            )
            if response.status_code == 400:
                payload = response.json()
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="renew_checkout",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload={"status_code": 400, "result": payload},
                )
                return payload
            if response.status_code == 404:
                payload = {"error": "Checkout not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="renew_checkout",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="renew_checkout",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="renew_checkout",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def return_item(instance_id: str, dropbox: bool = False) -> dict:
    """
    Process a return of a book instance.

    Args:
        instance_id: The ID of the book instance being returned
        dropbox: Whether this is a dropbox return

    Returns:
        Dictionary containing return confirmation
    """
    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="return_item",
        input_payload={"instance_id": instance_id, "dropbox": dropbox},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CIRCULATION_URL}/returns",
                json={"instance_id": instance_id, "dropbox": dropbox},
                headers=_auth_headers(),
            )
            if response.status_code == 400:
                payload = response.json()
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="return_item",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload={"status_code": 400, "result": payload},
                )
                return payload
            if response.status_code == 404:
                payload = {"error": "Item or active checkout not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="return_item",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="return_item",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="return_item",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def place_hold(book_id: str, patron_id: str) -> dict:
    """
    Place a hold on a book for a patron.

    Args:
        book_id: The ID of the book to hold
        patron_id: The ID of the patron placing the hold

    Returns:
        Dictionary containing hold confirmation or error
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="place_hold",
        input_payload={"book_id": book_id, "patron_id": patron_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CIRCULATION_URL}/holds",
                json={"book_id": book_id, "patron_id": patron_id},
                headers=_auth_headers(),
            )
            if response.status_code == 400:
                payload = response.json()
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="place_hold",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload={"status_code": 400, "result": payload},
                )
                return payload
            if response.status_code == 404:
                payload = {"error": "Book or patron not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="place_hold",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="place_hold",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="place_hold",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def cancel_hold(hold_id: str) -> dict:
    """
    Cancel an existing hold.

    Args:
        hold_id: The ID of the hold to cancel

    Returns:
        Dictionary containing cancellation confirmation
    """
    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="cancel_hold",
        input_payload={"hold_id": hold_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{CIRCULATION_URL}/holds/{hold_id}",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "Hold not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="cancel_hold",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = {"success": True, "message": "Hold cancelled"}
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="cancel_hold",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={
                    "status_code": response.status_code,
                    "result": payload,
                },
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="cancel_hold",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def get_patron_fines(patron_id: str) -> dict:
    """
    Get list of fines for a patron.

    Args:
        patron_id: The ID of the patron

    Returns:
        Dictionary containing list of fines
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="get_patron_fines",
        input_payload={"patron_id": patron_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CIRCULATION_URL}/patrons/{patron_id}/fines",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "Patron not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="get_patron_fines",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="get_patron_fines",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="get_patron_fines",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def pay_fine(fine_id: str, amount: Optional[float] = None) -> dict:
    """
    Pay a fine (full or partial payment).

    Args:
        fine_id: The ID of the fine to pay
        amount: Amount to pay (if None, pays full amount)

    Returns:
        Dictionary containing payment confirmation
    """
    call_id, started = begin_tool_call(
        source="agents.tools.circulation",
        tool_name="pay_fine",
        input_payload={"fine_id": fine_id, "amount": amount},
    )

    payload = {}
    if amount is not None:
        payload["amount"] = amount

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{CIRCULATION_URL}/fines/{fine_id}/pay",
                json=payload,
                headers=_auth_headers(),
            )
            if response.status_code == 400:
                result_payload = response.json()
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="pay_fine",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload={"status_code": 400, "result": result_payload},
                )
                return result_payload
            if response.status_code == 404:
                result_payload = {"error": "Fine not found"}
                end_tool_call(
                    source="agents.tools.circulation",
                    tool_name="pay_fine",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=result_payload,
                )
                return result_payload
            response.raise_for_status()
            result_payload = response.json()
            end_tool_call(
                source="agents.tools.circulation",
                tool_name="pay_fine",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={
                    "status_code": response.status_code,
                    "result": result_payload,
                },
            )
            return result_payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.circulation",
            tool_name="pay_fine",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


async def get_my_patron_summary() -> dict:
    """Get account summary for the currently active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )
    return await get_patron_summary(active_patron_id)


async def get_my_fines() -> dict:
    """Get fines for the currently active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )
    return await get_patron_fines(active_patron_id)


async def checkout_for_me(instance_id: str) -> dict:
    """Checkout a specific instance for the currently active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )
    return await checkout_item(instance_id=instance_id, patron_id=active_patron_id)


async def place_hold_for_me(book_id: str) -> dict:
    """Place a hold for the currently active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )
    return await place_hold(book_id=book_id, patron_id=active_patron_id)


# Tool definitions for Google ADK
CIRCULATION_TOOLS = [
    {
        "name": "get_my_patron_summary",
        "description": "Get the active patron's account summary (checkouts, holds, fines).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_my_fines",
        "description": "Get unpaid fines for the active patron profile.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "checkout_for_me",
        "description": "Check out a specific instance for the active patron profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "The book instance ID (e.g., 'inst-001-a')",
                }
            },
            "required": ["instance_id"],
        },
    },
    {
        "name": "place_hold_for_me",
        "description": "Place a hold for the active patron profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The book ID to hold (e.g., 'book-001')",
                }
            },
            "required": ["book_id"],
        },
    },
    {
        "name": "get_patron_summary",
        "description": "Get a patron's complete account summary including current checkouts, holds, and fines. Use this to see a patron's library status.",
        "parameters": {
            "type": "object",
            "properties": {
                "patron_id": {
                    "type": "string",
                    "description": "The patron's ID (e.g., 'patron-001')"
                }
            },
            "required": ["patron_id"]
        }
    },
    {
        "name": "checkout_item",
        "description": "Check out a book instance to a patron. Requires the specific instance ID and patron ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "The book instance ID (e.g., 'inst-001-a')"
                },
                "patron_id": {
                    "type": "string",
                    "description": "The patron's ID (e.g., 'patron-001')"
                }
            },
            "required": ["instance_id", "patron_id"]
        }
    },
    {
        "name": "renew_checkout",
        "description": "Renew an existing checkout. Renewals are allowed up to 2 times unless there are holds waiting.",
        "parameters": {
            "type": "object",
            "properties": {
                "checkout_id": {
                    "type": "string",
                    "description": "The checkout ID (e.g., 'checkout-inst-001-a')"
                }
            },
            "required": ["checkout_id"]
        }
    },
    {
        "name": "return_item",
        "description": "Process a book return. Any overdue fines will be calculated automatically.",
        "parameters": {
            "type": "object",
            "properties": {
                "instance_id": {
                    "type": "string",
                    "description": "The book instance ID being returned"
                },
                "dropbox": {
                    "type": "boolean",
                    "description": "Whether this is a dropbox return (affects fine calculation)"
                }
            },
            "required": ["instance_id"]
        }
    },
    {
        "name": "place_hold",
        "description": "Place a hold on a book for a patron. Useful when all copies are checked out.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The book ID to hold (e.g., 'book-001')"
                },
                "patron_id": {
                    "type": "string",
                    "description": "The patron's ID placing the hold"
                }
            },
            "required": ["book_id", "patron_id"]
        }
    },
    {
        "name": "cancel_hold",
        "description": "Cancel an existing hold on a book.",
        "parameters": {
            "type": "object",
            "properties": {
                "hold_id": {
                    "type": "string",
                    "description": "The hold ID to cancel"
                }
            },
            "required": ["hold_id"]
        }
    },
    {
        "name": "get_patron_fines",
        "description": "Get a list of unpaid fines for a patron.",
        "parameters": {
            "type": "object",
            "properties": {
                "patron_id": {
                    "type": "string",
                    "description": "The patron's ID"
                }
            },
            "required": ["patron_id"]
        }
    },
    {
        "name": "pay_fine",
        "description": "Pay a fine (fully or partially).",
        "parameters": {
            "type": "object",
            "properties": {
                "fine_id": {
                    "type": "string",
                    "description": "The fine ID to pay"
                },
                "amount": {
                    "type": "number",
                    "description": "Amount to pay (optional, pays full amount if not specified)"
                }
            },
            "required": ["fine_id"]
        }
    }
]
