"""Deterministic fault injection engine for chaos testing.

ChaosController intercepts service calls based on a FaultProfile's
call_index schedule.  Same seed + profile = identical fault sequence.

This is a **test utility only** — never imported by production code.
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any

from shared.http_client import ServiceCallError, ServiceUnavailableError

from chaos_profiles import FaultEvent, FaultProfile, FaultType


@dataclass
class FaultLogEntry:
    """Record of an injected fault."""

    call_index: int
    fault_type: str
    target_service: str
    target_endpoint: str
    timestamp: str


class ChaosController:
    """Deterministic fault injection controller.

    Tracks a per-(service, endpoint) call counter and fires faults
    when the counter matches a scheduled FaultEvent.call_index.
    """

    def __init__(self, profile: FaultProfile) -> None:
        self._profile = profile
        self._rng = random.Random(profile.seed)
        self._call_counters: dict[tuple[str, str], int] = {}
        self._fault_log: list[FaultLogEntry] = []
        self._retry_count = 0

        # Build a lookup: (service, endpoint, call_index) → FaultEvent
        self._schedule: dict[tuple[str, str, int], FaultEvent] = {}
        for event in profile.fault_events:
            key = (event.target_service, event.target_endpoint, event.call_index)
            self._schedule[key] = event

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def intercept(self, service: str, endpoint: str) -> FaultEvent | None:
        """Check whether the current call should be faulted.

        Increments the call counter for (service, endpoint) and returns
        the matching FaultEvent if one is scheduled, else None.
        """
        key = (service, endpoint)
        idx = self._call_counters.get(key, 0)
        self._call_counters[key] = idx + 1

        schedule_key = (service, endpoint, idx)
        return self._schedule.get(schedule_key)

    def apply_fault(self, event: FaultEvent) -> None:
        """Raise the appropriate exception for the given FaultEvent.

        For MALFORMED_JSON, raises ValueError (simulating bad decode).
        For all others, raises transport-level errors.
        """
        self._fault_log.append(
            FaultLogEntry(
                call_index=event.call_index,
                fault_type=event.fault_type.value,
                target_service=event.target_service,
                target_endpoint=event.target_endpoint,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

        if event.fault_type == FaultType.TIMEOUT:
            raise TimeoutError(
                f"Chaos: timeout on {event.target_service}{event.target_endpoint} "
                f"(call_index={event.call_index})"
            )

        if event.fault_type == FaultType.HTTP_500:
            raise ServiceCallError(
                f"Chaos: HTTP 500 from {event.target_service}{event.target_endpoint} "
                f"(call_index={event.call_index})",
                status_code=500,
            )

        if event.fault_type == FaultType.INTERMITTENT_OUTAGE:
            raise ServiceUnavailableError(
                f"Chaos: outage on {event.target_service}{event.target_endpoint} "
                f"(call_index={event.call_index})"
            )

        if event.fault_type == FaultType.CONNECTION_REFUSED:
            raise ConnectionError(
                f"Chaos: connection refused by {event.target_service}{event.target_endpoint} "
                f"(call_index={event.call_index})"
            )

        if event.fault_type == FaultType.MALFORMED_JSON:
            raise ValueError(
                f"Chaos: malformed JSON from {event.target_service}{event.target_endpoint} "
                f"(call_index={event.call_index})"
            )

        raise RuntimeError(f"Unsupported fault type: {event.fault_type}")

    def record_retry(self) -> None:
        """Record that a retry attempt was made (for budget tracking)."""
        self._retry_count += 1

    def reset(self) -> None:
        """Clear counters and logs for a fresh run."""
        self._call_counters.clear()
        self._fault_log.clear()
        self._retry_count = 0
        self._rng = random.Random(self._profile.seed)

    @property
    def fault_log(self) -> list[FaultLogEntry]:
        return list(self._fault_log)

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def retry_budget_check(self, max_budget: int | None = None) -> bool:
        """Return True if retries stayed within the allowed budget."""
        budget = max_budget if max_budget is not None else self._profile.max_retry_budget
        return self._retry_count <= budget

    def summary(self) -> dict[str, Any]:
        """Produce a chaos summary dict suitable for report embedding."""
        return {
            "profile_id": self._profile.profile_id,
            "seed": self._profile.seed,
            "total_faults_injected": len(self._fault_log),
            "total_retries": self._retry_count,
            "retry_budget": self._profile.max_retry_budget,
            "budget_respected": self.retry_budget_check(),
            "expected_degradation_mode": self._profile.expected_degradation_mode,
            "fault_log": [
                {
                    "call_index": e.call_index,
                    "fault_type": e.fault_type,
                    "target_service": e.target_service,
                    "target_endpoint": e.target_endpoint,
                    "timestamp": e.timestamp,
                }
                for e in self._fault_log
            ],
        }
