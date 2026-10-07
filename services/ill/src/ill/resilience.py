"""Lightweight async retry utility for the ILL service.

Provides ``@async_retry`` decorator with exponential backoff + jitter.
This is an ILL-local copy to avoid cross-package dependency on the
agents/ workspace member.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import random
from typing import Any, Callable, Sequence, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


def async_retry(
    *,
    max_attempts: int = 3,
    initial_delay: float = 0.2,
    max_delay: float = 5.0,
    jitter: bool = True,
    retryable_exceptions: Sequence[type[BaseException]] = (Exception,),
) -> Callable[[F], F]:
    """Decorator for async functions with exponential backoff + optional jitter.

    Args:
        max_attempts: Total attempts (including the first try).
        initial_delay: Base delay in seconds before the first retry.
        max_delay: Ceiling on computed delay.
        jitter: If True, add uniform random jitter up to 10% of delay.
        retryable_exceptions: Exception types eligible for retry.

    Raises:
        The last exception if all attempts are exhausted.
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_attempts):
                try:
                    return await fn(*args, **kwargs)
                except tuple(retryable_exceptions) as exc:
                    last_exc = exc
                    if attempt == max_attempts - 1:
                        raise
                    delay = min(initial_delay * (2 ** attempt), max_delay)
                    if jitter:
                        delay += random.uniform(0, delay * 0.1)
                    logger.warning(
                        "%s attempt %d/%d failed (%s), retrying in %.3fs",
                        fn.__name__,
                        attempt + 1,
                        max_attempts,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            # Unreachable, but keeps type-checkers satisfied.
            raise RuntimeError(f"Retry exhausted: {last_exc}")

        return wrapper  # type: ignore[return-value]

    return decorator
