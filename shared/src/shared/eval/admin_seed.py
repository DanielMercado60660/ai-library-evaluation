"""Shared helpers for admin reset-and-seed endpoints.

Each service includes a ``POST /admin/reset-and-seed`` route.  The
endpoint is gated behind the ``EVAL_MODE`` environment variable —
if ``EVAL_MODE`` is not ``true``, requests are rejected with 403.
"""

import os


def eval_mode_enabled() -> bool:
    """Return True when the service is running in eval mode."""
    return os.getenv("EVAL_MODE", "false").lower() in ("true", "1", "yes")
