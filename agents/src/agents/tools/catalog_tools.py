"""Tools for interacting with the catalog service."""

import httpx
from typing import Optional

from agents.config import CATALOG_URL
from agents.utils.resilience import with_retry
from shared.auth import SERVICE_TOKEN_HEADER, get_service_token
from shared.eval.runtime_trace import begin_tool_call, end_tool_call


def _auth_headers() -> dict[str, str]:
    return {SERVICE_TOKEN_HEADER: get_service_token()}


@with_retry(max_attempts=3)
async def search_books(
    query: str,
    genre: Optional[str] = None,
    author: Optional[str] = None,
    stratum: Optional[int] = None,
    series: Optional[str] = None,
    available_only: bool = False,
    limit: int = 10,
) -> dict:
    """
    Search the library catalog for books.

    Args:
        query: Search term to match against title, author, or summary
        genre: Filter by genre (optional)
        author: Filter by author name (optional)
        stratum: Filter by stratum 1-8 (optional):
            1=Noble Tragedies, 2=Histories, 3=Modern Lit, 4=Technical,
            5=Children's, 6=Poetry, 7=Philosophy, 8=Translated
        series: Filter by series name (optional)
        available_only: If True, only return books with available copies
        limit: Maximum number of results to return (default 10)

    Returns:
        Dictionary containing:
        - books: List of matching books with availability info
        - total: Total number of matches
    """
    call_id, started = begin_tool_call(
        source="agents.tools.catalog",
        tool_name="search_books",
        input_payload={
            "query": query,
            "genre": genre,
            "author": author,
            "stratum": stratum,
            "series": series,
            "available_only": available_only,
            "limit": limit,
        },
    )

    params = {"limit": limit}
    if query:
        params["q"] = query
    if genre:
        params["genre"] = genre
    if author:
        params["author"] = author
    if stratum:
        params["stratum"] = stratum
    if series:
        params["series"] = series
    if available_only:
        params["available"] = "true"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CATALOG_URL}/books",
                params=params,
                headers=_auth_headers(),
            )
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.catalog",
                tool_name="search_books",
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
            source="agents.tools.catalog",
            tool_name="search_books",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def get_book_details(book_id: str) -> dict:
    """
    Get detailed information about a specific book.

    Args:
        book_id: The unique identifier of the book

    Returns:
        Dictionary containing:
        - book: Book details (title, author, summary, etc.)
        - instances: List of physical copies and their status
        - total_copies: Total number of copies
        - available_copies: Number of available copies
    """
    call_id, started = begin_tool_call(
        source="agents.tools.catalog",
        tool_name="get_book_details",
        input_payload={"book_id": book_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CATALOG_URL}/books/{book_id}",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload = {"error": "Book not found"}
                end_tool_call(
                    source="agents.tools.catalog",
                    tool_name="get_book_details",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.catalog",
                tool_name="get_book_details",
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
            source="agents.tools.catalog",
            tool_name="get_book_details",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


@with_retry(max_attempts=3)
async def get_book_instances(book_id: str) -> list[dict]:
    """
    Get all physical instances of a book.

    Args:
        book_id: The unique identifier of the book

    Returns:
        List of book instances with status and location
    """
    call_id, started = begin_tool_call(
        source="agents.tools.catalog",
        tool_name="get_book_instances",
        input_payload={"book_id": book_id},
    )
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{CATALOG_URL}/books/{book_id}/instances",
                headers=_auth_headers(),
            )
            if response.status_code == 404:
                payload: list[dict] = []
                end_tool_call(
                    source="agents.tools.catalog",
                    tool_name="get_book_instances",
                    call_id=call_id,
                    started=started,
                    success=True,
                    output_payload=payload,
                )
                return payload
            response.raise_for_status()
            payload = response.json()
            end_tool_call(
                source="agents.tools.catalog",
                tool_name="get_book_instances",
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
            source="agents.tools.catalog",
            tool_name="get_book_instances",
            call_id=call_id,
            started=started,
            success=False,
            error=str(exc),
        )
        raise


# Tool definitions for Google ADK
CATALOG_TOOLS = [
    {
        "name": "search_books",
        "description": "Search the Hanno Memorial Library catalog for books. Searches title, author, and summary. Returns books with availability information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term to match against book titles, authors, or summaries"
                },
                "genre": {
                    "type": "string",
                    "description": "Filter results by genre (e.g., 'tragedy', 'historical fiction', 'children's fable')"
                },
                "author": {
                    "type": "string",
                    "description": "Filter results by author name (e.g., 'Maren Greyhorn', 'Penelope Trunkling')"
                },
                "stratum": {
                    "type": "integer",
                    "description": "Filter by catalog stratum: 1=Noble Tragedies, 2=Histories, 3=Modern Lit, 4=Technical, 5=Children's, 6=Poetry, 7=Philosophy, 8=Translated"
                },
                "series": {
                    "type": "string",
                    "description": "Filter by series name (e.g., 'The Chronicles of the Ivory Age')"
                },
                "available_only": {
                    "type": "boolean",
                    "description": "If true, only return books that have available copies"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_book_details",
        "description": "Get detailed information about a specific book, including all physical copies, their availability status, shelf location, and condition.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The unique identifier of the book (e.g., 'book-001')"
                }
            },
            "required": ["book_id"]
        }
    }
]
