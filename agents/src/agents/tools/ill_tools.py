"""Tools for interacting with the ILL (Inter-Library Loan) service."""

import httpx
from typing import Optional

from agents.config import RECOMMENDATION_URL
from agents.session.active_patron_context import get_active_patron_context
from agents.utils.resilience import with_retry
from shared.auth import SERVICE_TOKEN_HEADER, get_service_token
from shared.eval.runtime_trace import begin_tool_call, end_tool_call


def _auth_headers() -> dict[str, str]:
    return {SERVICE_TOKEN_HEADER: get_service_token()}


def _resolve_active_patron_id() -> str | None:
    context = get_active_patron_context()
    return context.patron_id if context else None


def _policy_error(message: str) -> dict:
    return {"error": message}


def _enforce_active_patron_match(patron_id: str) -> dict | None:
    active_patron_id = _resolve_active_patron_id()
    if active_patron_id and patron_id != active_patron_id:
        return _policy_error(
            "ILL account actions are bound to the active profile. "
            "Switch active patron profile and retry."
        )
    return None


ILL_URL = RECOMMENDATION_URL  # ILL service shares the RECOMMENDATION_URL config (port 8003).


@with_retry(max_attempts=3)
async def create_ill_request(
    book_id: str,
    patron_id: str,
    source_library: str,
    notes: str = "",
) -> dict:
    """
    Create an inter-library loan request for a book not in our collection.

    Args:
        book_id: The identifier of the book to request
        patron_id: The patron making the request
        source_library: The library code to borrow from (e.g., 'mastodon-institute')
        notes: Optional notes for the request

    Returns:
        Dictionary containing the created ILL request details
    """
    policy_error = _enforce_active_patron_match(patron_id)
    if policy_error:
        return policy_error

    call_id, started = begin_tool_call(
        source="agents.tools.ill",
        tool_name="create_ill_request",
        input_payload={
            "book_id": book_id,
            "patron_id": patron_id,
            "source_library": source_library,
            "notes": notes,
        },
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ILL_URL}/requests",
                json={
                    "book_id": book_id,
                    "patron_id": patron_id,
                    "source_library": source_library,
                    "notes": notes,
                },
                headers=_auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.ill",
                tool_name="create_ill_request",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.ill",
            tool_name="create_ill_request",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def get_ill_request_status(request_id: str) -> dict:
    """
    Check the status of an inter-library loan request.

    Args:
        request_id: The unique identifier of the ILL request

    Returns:
        Dictionary containing the ILL request status and details
    """
    call_id, started = begin_tool_call(
        source="agents.tools.ill",
        tool_name="get_ill_request_status",
        input_payload={"request_id": request_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ILL_URL}/requests/{request_id}",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "ILL request not found"}
                end_tool_call(
                    source="agents.tools.ill",
                    tool_name="get_ill_request_status",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.ill",
                tool_name="get_ill_request_status",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.ill",
            tool_name="get_ill_request_status",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def list_partner_libraries() -> dict:
    """
    List available partner libraries in the Great Herd Library System.

    Returns:
        Dictionary containing:
        - libraries: List of partner libraries with codes, names, and status
    """
    from agents.config import AUTH_URL  # Registry service URL

    call_id, started = begin_tool_call(
        source="agents.tools.ill",
        tool_name="list_partner_libraries",
        input_payload={},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AUTH_URL}/libraries", headers=_auth_headers())
            if response.status_code == 404:
                payload = {"libraries": []}
                end_tool_call(
                    source="agents.tools.ill",
                    tool_name="list_partner_libraries",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.ill",
                tool_name="list_partner_libraries",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return payload
    except Exception as exc:
        end_tool_call(
            source="agents.tools.ill",
            tool_name="list_partner_libraries",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def search_partner_catalog(
    library_code: str,
    query: str = "",
    limit: int = 10,
) -> dict:
    """
    Search a partner library's catalog for books.

    First resolves the partner's catalog URL from the registry,
    then queries their catalog service.

    Args:
        library_code: The partner library code (e.g., 'mastodon-institute')
        query: Search term to match against titles, authors, or summaries
        limit: Maximum results to return (default 10)

    Returns:
        Dictionary with books found at the partner library, or error message
    """
    call_id, started = begin_tool_call(
        source="agents.tools.ill",
        tool_name="search_partner_catalog",
        input_payload={
            "library_code": library_code,
            "query": query,
            "limit": limit,
        },
    )
    from agents.config import AUTH_URL

    try:
        async with httpx.AsyncClient() as client:
            # Resolve catalog URL from registry
            reg_resp = await client.get(f"{AUTH_URL}/libraries", headers=_auth_headers())
            reg_resp.raise_for_status()
            libraries = reg_resp.json()

            catalog_url = None
            for lib in libraries:
                if lib.get("code") == library_code:
                    catalog_url = lib.get("catalog_url")
                    break

            if not catalog_url:
                payload = {
                    "error": f"No catalog URL found for library '{library_code}'"
                }
                end_tool_call(
                    source="agents.tools.ill",
                    tool_name="search_partner_catalog",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload

            # Query the partner catalog
            params: dict = {"limit": limit}
            if query:
                params["q"] = query
            resp = await client.get(
                f"{catalog_url}/books",
                params=params,
                headers=_auth_headers(),
            )
            if resp.status_code == 404:
                payload = {"books": [], "total": 0, "library": library_code}
                end_tool_call(
                    source="agents.tools.ill",
                    tool_name="search_partner_catalog",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            resp.raise_for_status()
            data = resp.json()
            data["library"] = library_code
            end_tool_call(
                source="agents.tools.ill",
                tool_name="search_partner_catalog",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": resp.status_code, "result": data},
            )
            return data
    except Exception as exc:
        end_tool_call(
            source="agents.tools.ill",
            tool_name="search_partner_catalog",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def list_my_ill_requests(status: str | None = None) -> dict:
    """List ILL requests for the active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )

    call_id, started = begin_tool_call(
        source="agents.tools.ill",
        tool_name="list_my_ill_requests",
        input_payload={"status": status, "patron_id": active_patron_id},
    )
    try:
        params: dict[str, str] = {"patron_id": active_patron_id}
        if status:
            params["status"] = status
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ILL_URL}/requests",
                params=params,
                headers=_auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.ill",
                tool_name="list_my_ill_requests",
                call_id=call_id,
                started=started,
                success=True,
                output_payload={"status_code": response.status_code, "result": payload},
            )
            return {"requests": payload}
    except Exception as exc:
        end_tool_call(
            source="agents.tools.ill",
            tool_name="list_my_ill_requests",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


async def create_ill_request_for_me(
    book_id: str,
    source_library: str,
    notes: str = "",
) -> dict:
    """Create an ILL request for the active patron profile."""
    active_patron_id = _resolve_active_patron_id()
    if not active_patron_id:
        return _policy_error(
            "No active patron profile is bound to this request. "
            "Switch to a patron profile and retry."
        )
    return await create_ill_request(
        book_id=book_id,
        patron_id=active_patron_id,
        source_library=source_library,
        notes=notes,
    )


# Tool definitions for Google ADK
ILL_TOOLS = [
    {
        "name": "list_my_ill_requests",
        "description": "List ILL requests for the currently active patron profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "Optional status filter (pending, approved, shipped, etc.)",
                },
            },
            "required": [],
        },
    },
    {
        "name": "create_ill_request_for_me",
        "description": "Create an ILL request for the active patron profile.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The identifier of the book to request from the partner library",
                },
                "source_library": {
                    "type": "string",
                    "description": "The library code to borrow from",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes for the ILL request",
                },
            },
            "required": ["book_id", "source_library"],
        },
    },
    {
        "name": "create_ill_request",
        "description": "Create an inter-library loan request to borrow a book from another library in the Great Herd Library System.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The identifier of the book to request from the partner library",
                },
                "patron_id": {
                    "type": "string",
                    "description": "The patron ID making the request",
                },
                "source_library": {
                    "type": "string",
                    "description": "The library code to borrow from (e.g., 'mastodon-institute', 'mammoth-valley', 'ivory-university')",
                },
                "notes": {
                    "type": "string",
                    "description": "Optional notes for the ILL request",
                },
            },
            "required": ["book_id", "patron_id", "source_library"],
        },
    },
    {
        "name": "get_ill_request_status",
        "description": "Check the current status of an inter-library loan request.",
        "parameters": {
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "The unique identifier of the ILL request to check",
                },
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "list_partner_libraries",
        "description": "List all partner libraries in the Great Herd Library System that we can borrow from.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_partner_catalog",
        "description": "Search a specific partner library's catalog to find books available for inter-library loan. Use this BEFORE creating an ILL request to check if the partner has the book.",
        "parameters": {
            "type": "object",
            "properties": {
                "library_code": {
                    "type": "string",
                    "description": "The partner library code (e.g., 'mastodon-institute', 'mammoth-valley', 'ivory-university', 'tusk-conservatory')",
                },
                "query": {
                    "type": "string",
                    "description": "Search term to find books by title, author, or content",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default 10)",
                },
            },
            "required": ["library_code"],
        },
    },
]
