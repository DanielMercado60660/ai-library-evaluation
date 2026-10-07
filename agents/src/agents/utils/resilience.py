"""Resilience utilities for the AI Library agents.

Provides:
- Retry decorator with exponential backoff
- Circuit breaker pattern for service calls
- Error classification helpers
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Callable, TypeVar, Any, Tuple, Type

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _is_client_error(exc: Exception) -> bool:
    """Return True for HTTP 4xx errors that should NOT be retried."""
    if isinstance(exc, httpx.HTTPStatusError):
        return 400 <= exc.response.status_code < 500
    return False


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and call is rejected."""

    def __init__(self, service_name: str, recovery_time: float):
        self.service_name = service_name
        self.recovery_time = recovery_time
        super().__init__(
            f"Circuit breaker for '{service_name}' is open. "
            f"Recovery in {recovery_time:.1f}s"
        )


# Default retryable exceptions
DEFAULT_RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    ConnectionError,
    TimeoutError,
    httpx.HTTPError,
    httpx.TimeoutException,
    httpx.ConnectError,
)


def with_retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
    on_retry: Callable[[Exception, int], None] | None = None,
):
    """Decorator for async functions with retry and exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exception types that trigger retry
        on_retry: Optional callback called on each retry (exception, attempt)

    Usage:
        @with_retry(max_attempts=3)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                return response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    # Don't retry 4xx client errors — they won't succeed on retry
                    if _is_client_error(e):
                        raise
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): "
                            f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                        )
                        if on_retry:
                            on_retry(e, attempt + 1)
                        await asyncio.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: "
                            f"{type(e).__name__}: {e}"
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry decorator")

        return wrapper

    return decorator


def with_retry_sync(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = DEFAULT_RETRYABLE_EXCEPTIONS,
):
    """Decorator for sync functions with retry and exponential backoff.

    Same as with_retry but for synchronous functions.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = initial_delay
            last_exception: Exception | None = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    # Don't retry 4xx client errors — they won't succeed on retry
                    if _is_client_error(e):
                        raise
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_attempts}): "
                            f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * exponential_base, max_delay)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: "
                            f"{type(e).__name__}: {e}"
                        )

            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected state in retry decorator")

        return wrapper

    return decorator


class CircuitBreaker:
    """Circuit breaker for protecting service calls.

    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Calls are rejected immediately
    - HALF_OPEN: Test call allowed to check if service recovered

    Usage:
        breaker = CircuitBreaker(name="catalog-service")

        async def fetch_catalog():
            return await breaker.call(catalog_client.search, query="tragedy")

        # Or as context manager:
        async with breaker:
            result = await catalog_client.search(query="tragedy")
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        """Initialize circuit breaker.

        Args:
            name: Name for logging and identification
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds to wait before attempting recovery
            half_open_max_calls: Max calls allowed in half-open state
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures = 0
        self._last_failure_time: float | None = None
        self._state = self.CLOSED
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed (normal operation)."""
        return self._state == self.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open (rejecting calls)."""
        return self._state == self.OPEN

    async def __aenter__(self):
        """Enter async context - check if call is allowed."""
        self._check_state()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - record result."""
        if exc_type is None:
            self._on_success()
        else:
            self._on_failure()
        return False  # Don't suppress exceptions

    def _check_state(self) -> None:
        """Check state and potentially transition, raise if open."""
        if self._state == self.OPEN:
            if self._should_attempt_recovery():
                logger.info(f"Circuit breaker '{self.name}' entering half-open state")
                self._state = self.HALF_OPEN
                self._half_open_calls = 0
            else:
                time_since_failure = time.time() - (self._last_failure_time or 0)
                recovery_remaining = self.recovery_timeout - time_since_failure
                raise CircuitBreakerOpenError(self.name, recovery_remaining)

        if self._state == self.HALF_OPEN:
            if self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpenError(self.name, self.recovery_timeout)
            self._half_open_calls += 1

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def _on_success(self) -> None:
        """Record successful call."""
        if self._state == self.HALF_OPEN:
            logger.info(f"Circuit breaker '{self.name}' recovered, closing")
        self._failures = 0
        self._state = self.CLOSED
        self._half_open_calls = 0

    def _on_failure(self) -> None:
        """Record failed call."""
        self._failures += 1
        self._last_failure_time = time.time()

        if self._state == self.HALF_OPEN:
            logger.warning(f"Circuit breaker '{self.name}' reopening after failed recovery")
            self._state = self.OPEN

        elif self._failures >= self.failure_threshold:
            logger.warning(
                f"Circuit breaker '{self.name}' opening after {self._failures} failures"
            )
            self._state = self.OPEN

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute a function through the circuit breaker.

        Args:
            func: Async function to call
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Any exception from func
        """
        self._check_state()

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self._failures = 0
        self._last_failure_time = None
        self._state = self.CLOSED
        self._half_open_calls = 0


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers.

    Usage:
        registry = CircuitBreakerRegistry()
        catalog_breaker = registry.get_or_create("catalog-service")
        circulation_breaker = registry.get_or_create("circulation-service")
    """

    def __init__(
        self,
        default_failure_threshold: int = 5,
        default_recovery_timeout: float = 30.0,
    ):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._default_failure_threshold = default_failure_threshold
        self._default_recovery_timeout = default_recovery_timeout

    def get_or_create(
        self,
        name: str,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
    ) -> CircuitBreaker:
        """Get or create a circuit breaker by name."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold or self._default_failure_threshold,
                recovery_timeout=recovery_timeout or self._default_recovery_timeout,
            )
        return self._breakers[name]

    def get(self, name: str) -> CircuitBreaker | None:
        """Get a circuit breaker by name if it exists."""
        return self._breakers.get(name)

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    @property
    def status(self) -> dict[str, str]:
        """Get status of all circuit breakers."""
        return {name: breaker.state for name, breaker in self._breakers.items()}


# Global registry instance
circuit_breaker_registry = CircuitBreakerRegistry()
