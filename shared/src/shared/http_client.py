"""HTTP client for inter-service communication.

Provides a consistent interface for services to communicate with each other
via HTTP, with proper error handling and logging.
"""

import logging
from typing import Any, Literal
import httpx

from shared.auth import SERVICE_TOKEN_HEADER, get_service_token
from shared.observability import CORRELATION_HEADER, RUN_ID_HEADER, get_correlation_id, get_run_id
from shared.service_registry import ServiceName, get_service_url

logger = logging.getLogger(__name__)

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE"]


class ServiceCallError(Exception):
    """Base exception for service call errors."""

    def __init__(
        self,
        message: str,
        service: str,
        endpoint: str,
        status_code: int | None = None,
        response_body: Any = None,
    ):
        super().__init__(message)
        self.service = service
        self.endpoint = endpoint
        self.status_code = status_code
        self.response_body = response_body


class ServiceNotFoundError(ServiceCallError):
    """Raised when a service returns 404."""

    pass


class ServiceUnavailableError(ServiceCallError):
    """Raised when a service is unreachable or returns 5xx."""

    pass


class ServiceBadRequestError(ServiceCallError):
    """Raised when a service returns 4xx (except 404)."""

    pass


async def call_service(
    service: ServiceName,
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> Any:
    """Call another service via HTTP.

    Args:
        service: Name of the service to call (catalog, circulation, ill)
        endpoint: API endpoint path (e.g., "/books/123")
        method: HTTP method (GET, POST, PUT, PATCH, DELETE)
        data: JSON data to send in request body (for POST/PUT/PATCH)
        params: Query parameters
        headers: Optional HTTP headers
        timeout: Request timeout in seconds

    Returns:
        JSON response from the service

    Raises:
        ServiceNotFoundError: Service returned 404
        ServiceBadRequestError: Service returned 4xx error
        ServiceUnavailableError: Service is unreachable or returned 5xx
        ServiceCallError: Other errors

    Example:
        >>> # Get a book from catalog
        >>> book = await call_service("catalog", "/books/123")
        >>>
        >>> # Create a checkout in circulation
        >>> checkout = await call_service(
        ...     "circulation",
        ...     "/checkouts",
        ...     method="POST",
        ...     data={"patron_id": "P001", "instance_id": "I001"}
        ... )
    """
    base_url = get_service_url(service)
    url = f"{base_url}{endpoint}"

    logger.info(
        f"Calling {service} service: {method} {endpoint}",
        extra={"service": service, "method": method, "endpoint": endpoint},
    )

    effective_headers: dict[str, str] = {
        SERVICE_TOKEN_HEADER: get_service_token(),
    }
    cid = get_correlation_id()
    if cid:
        effective_headers[CORRELATION_HEADER] = cid
    rid = get_run_id()
    if rid:
        effective_headers[RUN_ID_HEADER] = rid
    if headers:
        effective_headers.update(headers)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Choose method
            if method == "GET":
                response = await client.get(url, params=params, headers=effective_headers)
            elif method == "POST":
                response = await client.post(url, json=data, params=params, headers=effective_headers)
            elif method == "PUT":
                response = await client.put(url, json=data, params=params, headers=effective_headers)
            elif method == "PATCH":
                response = await client.patch(url, json=data, params=params, headers=effective_headers)
            elif method == "DELETE":
                response = await client.delete(url, params=params, headers=effective_headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            # Handle errors
            if response.status_code == 404:
                error_detail = _extract_error_detail(response)
                raise ServiceNotFoundError(
                    f"{service} service returned 404: {error_detail}",
                    service=service,
                    endpoint=endpoint,
                    status_code=404,
                    response_body=response.text,
                )

            if 400 <= response.status_code < 500:
                error_detail = _extract_error_detail(response)
                raise ServiceBadRequestError(
                    f"{service} service returned {response.status_code}: {error_detail}",
                    service=service,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            if response.status_code >= 500:
                error_detail = _extract_error_detail(response)
                raise ServiceUnavailableError(
                    f"{service} service returned {response.status_code}: {error_detail}",
                    service=service,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            # Raise for any other non-2xx status
            response.raise_for_status()

            # Parse and return JSON
            return response.json()

    except httpx.TimeoutException as e:
        logger.error(f"Timeout calling {service} service: {endpoint}")
        raise ServiceUnavailableError(
            f"{service} service timed out after {timeout}s",
            service=service,
            endpoint=endpoint,
        ) from e

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to {service} service: {url}")
        raise ServiceUnavailableError(
            f"Cannot connect to {service} service at {url}",
            service=service,
            endpoint=endpoint,
        ) from e

    except (ServiceCallError, ValueError):
        # Re-raise our custom exceptions and value errors
        raise

    except Exception as e:
        logger.error(
            f"Unexpected error calling {service} service: {e}",
            exc_info=True,
        )
        raise ServiceCallError(
            f"Unexpected error calling {service} service: {str(e)}",
            service=service,
            endpoint=endpoint,
        ) from e


def _extract_error_detail(response: httpx.Response) -> str:
    """Extract error detail from response.

    Attempts to parse JSON error response, falls back to text.
    """
    try:
        error_json = response.json()
        # FastAPI returns {"detail": "error message"}
        if isinstance(error_json, dict) and "detail" in error_json:
            return error_json["detail"]
        return str(error_json)
    except Exception:
        return response.text or "No error detail"


# Convenience functions for specific services
async def call_catalog(
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call the Catalog service."""
    return await call_service("catalog", endpoint, method, data, params)


async def call_circulation(
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call the Circulation service."""
    return await call_service("circulation", endpoint, method, data, params)


async def call_ill(
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call the ILL service."""
    return await call_service("ill", endpoint, method, data, params)


async def call_registry(
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> Any:
    """Call the Registry service."""
    return await call_service("registry", endpoint, method, data, params)


async def call_url(
    base_url: str,
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> Any:
    """Call an arbitrary URL directly (for spoke catalog resolution).

    Same error handling as call_service() but takes an explicit base URL
    instead of resolving via ServiceRegistry.
    """
    url = f"{base_url.rstrip('/')}{endpoint}"
    service_label = base_url  # used in error messages

    logger.info(f"Calling URL: {method} {url}")

    effective_headers: dict[str, str] = {
        SERVICE_TOKEN_HEADER: get_service_token(),
    }
    cid = get_correlation_id()
    if cid:
        effective_headers[CORRELATION_HEADER] = cid
    rid = get_run_id()
    if rid:
        effective_headers[RUN_ID_HEADER] = rid

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "GET":
                response = await client.get(url, params=params, headers=effective_headers)
            elif method == "POST":
                response = await client.post(url, json=data, params=params, headers=effective_headers)
            elif method == "PUT":
                response = await client.put(url, json=data, params=params, headers=effective_headers)
            elif method == "PATCH":
                response = await client.patch(url, json=data, params=params, headers=effective_headers)
            elif method == "DELETE":
                response = await client.delete(url, params=params, headers=effective_headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 404:
                error_detail = _extract_error_detail(response)
                raise ServiceNotFoundError(
                    f"Remote service returned 404: {error_detail}",
                    service=service_label,
                    endpoint=endpoint,
                    status_code=404,
                    response_body=response.text,
                )

            if 400 <= response.status_code < 500:
                error_detail = _extract_error_detail(response)
                raise ServiceBadRequestError(
                    f"Remote service returned {response.status_code}: {error_detail}",
                    service=service_label,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            if response.status_code >= 500:
                error_detail = _extract_error_detail(response)
                raise ServiceUnavailableError(
                    f"Remote service returned {response.status_code}: {error_detail}",
                    service=service_label,
                    endpoint=endpoint,
                    status_code=response.status_code,
                    response_body=response.text,
                )

            response.raise_for_status()
            return response.json()

    except httpx.TimeoutException as e:
        logger.error(f"Timeout calling {url}")
        raise ServiceUnavailableError(
            f"Remote service timed out after {timeout}s",
            service=service_label,
            endpoint=endpoint,
        ) from e

    except httpx.ConnectError as e:
        logger.error(f"Cannot connect to {url}")
        raise ServiceUnavailableError(
            f"Cannot connect to remote service at {url}",
            service=service_label,
            endpoint=endpoint,
        ) from e

    except (ServiceCallError, ValueError):
        raise

    except Exception as e:
        logger.error(f"Unexpected error calling {url}: {e}", exc_info=True)
        raise ServiceCallError(
            f"Unexpected error calling remote service: {str(e)}",
            service=service_label,
            endpoint=endpoint,
        ) from e


async def call_remote_catalog(
    catalog_url: str,
    endpoint: str,
    method: HttpMethod = "GET",
    data: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> Any:
    """Call a remote catalog service by its direct URL."""
    return await call_url(catalog_url, endpoint, method, data, params, timeout)
