"""A2A client utilities for ILL service.

Retry semantics (v1.3):
    - ``send_a2a_message`` uses exponential back-off with jitter via
      ``@async_retry`` from ``ill.resilience``.
    - Retryable: ``ServiceUnavailableError`` (transient).
    - Non-retryable: ``ServiceCallError`` (validation / non-transient).
    - Default schedule: 3 attempts, delays ~0.2s → 0.4s → capped at 5s,
      plus up to 10 % jitter per attempt.
"""

import os
from typing import Any

from shared.a2a.schemas import A2AMessageEnvelope, A2AMessageType
from shared.http_client import call_service, ServiceCallError, ServiceUnavailableError

from ill.resilience import async_retry


LOCAL_LIBRARY_CODE = os.getenv("A2A_LIBRARY_CODE", "hanno-memorial")
DEFAULT_RETRIES = 2
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_RETRY_DELAY_SECONDS = 0.2

# PII field names that must never appear in outbound A2A payloads.
PROHIBITED_PAYLOAD_FIELDS = frozenset({
    "email",
    "phone",
    "ssn",
    "address",
    "card_number",
    "patron_email",
    "patron_phone",
    "patron_address",
    "patron_ssn",
})


def _validate_outbound_payload(payload: dict[str, Any]) -> None:
    """Reject outbound A2A payloads containing PII-sensitive fields.

    Raises:
        ValueError: If any prohibited field name is found in the payload keys.
    """
    violations = PROHIBITED_PAYLOAD_FIELDS & set(payload.keys())
    if violations:
        raise ValueError(
            f"A2A payload contains prohibited PII fields: {sorted(violations)}"
        )


async def send_a2a_message(
    *,
    to_library: str,
    message_type: A2AMessageType,
    payload: dict[str, Any],
    correlation_id: str | None = None,
    retries: int = DEFAULT_RETRIES,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
) -> dict[str, Any]:
    """Send one A2A message via registry relay with bounded retries.

    Retry behaviour:
        ``max_attempts = retries + 1`` (backward-compatible with the old
        ``retries`` parameter).  Exponential back-off with jitter; only
        ``ServiceUnavailableError`` is retried.  ``ServiceCallError``
        (non-transient) fails immediately.
    """
    _validate_outbound_payload(payload)
    message = A2AMessageEnvelope(
        type=message_type,
        from_library=LOCAL_LIBRARY_CODE,
        to_library=to_library,
        correlation_id=correlation_id,
        payload=payload,
    )

    @async_retry(
        max_attempts=retries + 1,
        initial_delay=retry_delay_seconds,
        max_delay=timeout_seconds,
        jitter=True,
        retryable_exceptions=(ServiceUnavailableError,),
    )
    async def _do_send() -> dict[str, Any]:
        return await call_service(
            "registry",
            "/a2a/message/send",
            method="POST",
            data={"message": message.model_dump(mode="json")},
            headers={"x-library-code": LOCAL_LIBRARY_CODE},
            timeout=timeout_seconds,
        )

    return await _do_send()
