"""Shared schemas and utilities for AI Library."""

from shared.schemas import (
    Book,
    BookInstance,
    Patron,
    Checkout,
    Hold,
)
from shared.constants import InstanceStatus, CheckoutStatus
from shared.service_registry import ServiceRegistry, get_service_url
from shared.http_client import (
    call_service,
    call_catalog,
    call_circulation,
    call_ill,
    ServiceCallError,
    ServiceNotFoundError,
    ServiceUnavailableError,
    ServiceBadRequestError,
)
from shared.a2a.schemas import (
    A2AMessageType,
    A2AMessageEnvelope,
    A2ASendRequest,
    A2ASendResponse,
    A2AInboxResponse,
    A2AAckRequest,
    A2AAckResponse,
)
from shared.eval.trace_schemas import (
    TraceEvent,
    TraceEventType,
    TraceSummary,
    ForensicSeverity,
    ForensicAssertionResult,
    ForensicAssertionReport,
)
from shared.eval.trace_writer import TraceWriter
from shared.eval.scenario_steps import (
    build_default_scenario_steps,
    derive_step_outcomes,
)
from shared.eval.runtime_trace import (
    runtime_trace_enabled,
    get_active_scenario_id,
    summarize_for_trace,
    begin_tool_call,
    end_tool_call,
    emit_runtime_event,
)
from shared.auth import (
    get_service_token,
    ServiceAuthMiddleware,
    SERVICE_TOKEN_HEADER,
    PUBLIC_PATH_PREFIXES,
)
from shared.observability import (
    get_correlation_id,
    get_run_id,
    RequestCorrelationMiddleware,
    StructuredLogEvent,
    CORRELATION_HEADER,
    RUN_ID_HEADER,
)

__all__ = [
    # Schemas
    "Book",
    "BookInstance",
    "Patron",
    "Checkout",
    "Hold",
    # Constants
    "InstanceStatus",
    "CheckoutStatus",
    # Service registry
    "ServiceRegistry",
    "get_service_url",
    # HTTP client
    "call_service",
    "call_catalog",
    "call_circulation",
    "call_ill",
    "ServiceCallError",
    "ServiceNotFoundError",
    "ServiceUnavailableError",
    "ServiceBadRequestError",
    # A2A
    "A2AMessageType",
    "A2AMessageEnvelope",
    "A2ASendRequest",
    "A2ASendResponse",
    "A2AInboxResponse",
    "A2AAckRequest",
    "A2AAckResponse",
    # Eval
    "TraceEvent",
    "TraceEventType",
    "TraceSummary",
    "ForensicSeverity",
    "ForensicAssertionResult",
    "ForensicAssertionReport",
    "TraceWriter",
    "build_default_scenario_steps",
    "derive_step_outcomes",
    "runtime_trace_enabled",
    "get_active_scenario_id",
    "summarize_for_trace",
    "begin_tool_call",
    "end_tool_call",
    "emit_runtime_event",
    # Auth
    "get_service_token",
    "ServiceAuthMiddleware",
    "SERVICE_TOKEN_HEADER",
    "PUBLIC_PATH_PREFIXES",
    # Observability
    "get_correlation_id",
    "get_run_id",
    "RequestCorrelationMiddleware",
    "StructuredLogEvent",
    "CORRELATION_HEADER",
    "RUN_ID_HEADER",
]
