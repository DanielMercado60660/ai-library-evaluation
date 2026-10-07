"""Active patron context for request-scoped identity binding.

This module exposes a ContextVar-backed context manager so agent tools can
resolve the currently active patron profile for "self" actions.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Iterator


@dataclass(slots=True, frozen=True)
class ActivePatronContext:
    """Request-scoped active patron identity."""

    patron_id: str
    name: str | None = None
    role: str | None = None


_ACTIVE_PATRON_CONTEXT: ContextVar[ActivePatronContext | None] = ContextVar(
    "active_patron_context",
    default=None,
)


def get_active_patron_context() -> ActivePatronContext | None:
    """Return the active patron context for the current task."""
    return _ACTIVE_PATRON_CONTEXT.get()


def get_active_patron_id() -> str | None:
    """Return active patron id when available."""
    context = get_active_patron_context()
    return context.patron_id if context else None


@contextmanager
def bind_active_patron_context(
    patron_id: str | None,
    *,
    name: str | None = None,
    role: str | None = None,
) -> Iterator[None]:
    """Bind active patron context for the duration of a request scope."""
    if patron_id:
        token = _ACTIVE_PATRON_CONTEXT.set(
            ActivePatronContext(
                patron_id=patron_id,
                name=name,
                role=role,
            )
        )
    else:
        token = _ACTIVE_PATRON_CONTEXT.set(None)

    try:
        yield
    finally:
        _ACTIVE_PATRON_CONTEXT.reset(token)
