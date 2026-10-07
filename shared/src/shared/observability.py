"""Observability primitives for request correlation and structured logging.

Provides ContextVar-based correlation ID propagation, a structured log
event schema, and middleware to generate/echo correlation headers.
"""

import uuid
from contextvars import ContextVar
from typing import Optional

from pydantic import BaseModel, Field
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

CORRELATION_HEADER = "x-request-id"
RUN_ID_HEADER = "x-run-id"

correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
run_id_var: ContextVar[Optional[str]] = ContextVar("run_id", default=None)


def get_correlation_id() -> Optional[str]:
    """Return the current request's correlation ID, if set."""
    return correlation_id_var.get()


def get_run_id() -> Optional[str]:
    """Return the current request's benchmark run ID, if set."""
    return run_id_var.get()


class StructuredLogEvent(BaseModel):
    """Schema for structured log events (v1.8)."""

    timestamp: str
    level: str
    logger: str
    message: str
    correlation_id: Optional[str] = None
    run_id: Optional[str] = None
    service: Optional[str] = None
    extra: Optional[dict] = Field(default=None)


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Generate or propagate X-Request-ID and optional X-Run-ID headers.

    Sets ContextVars for downstream use and echoes correlation ID in response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        cid = request.headers.get(CORRELATION_HEADER) or str(uuid.uuid4())
        rid = request.headers.get(RUN_ID_HEADER)

        cid_token = correlation_id_var.set(cid)
        rid_token = run_id_var.set(rid)

        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = cid
            if rid:
                response.headers[RUN_ID_HEADER] = rid
            return response
        finally:
            correlation_id_var.reset(cid_token)
            run_id_var.reset(rid_token)
