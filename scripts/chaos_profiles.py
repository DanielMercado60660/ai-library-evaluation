"""Fault profile schema and built-in profiles for deterministic chaos testing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


class FaultType(str, Enum):
    """Types of faults that can be injected."""

    TIMEOUT = "timeout"
    HTTP_500 = "http_500"
    MALFORMED_JSON = "malformed_json"
    INTERMITTENT_OUTAGE = "intermittent_outage"
    CONNECTION_REFUSED = "connection_refused"


@dataclass(slots=True)
class FaultEvent:
    """A single fault to inject at a specific call index."""

    call_index: int
    fault_type: FaultType
    target_service: str
    target_endpoint: str
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["fault_type"] = self.fault_type.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FaultEvent:
        return cls(
            call_index=data["call_index"],
            fault_type=FaultType(data["fault_type"]),
            target_service=data["target_service"],
            target_endpoint=data["target_endpoint"],
            duration_ms=data.get("duration_ms", 0),
        )


@dataclass(slots=True)
class FaultProfile:
    """Deterministic fault injection profile."""

    profile_id: str
    seed: int
    description: str
    fault_events: list[FaultEvent] = field(default_factory=list)
    max_retry_budget: int = 5
    expected_degradation_mode: str = "graceful"

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "seed": self.seed,
            "description": self.description,
            "fault_events": [e.to_dict() for e in self.fault_events],
            "max_retry_budget": self.max_retry_budget,
            "expected_degradation_mode": self.expected_degradation_mode,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FaultProfile:
        return cls(
            profile_id=data["profile_id"],
            seed=data["seed"],
            description=data["description"],
            fault_events=[FaultEvent.from_dict(e) for e in data.get("fault_events", [])],
            max_retry_budget=data.get("max_retry_budget", 5),
            expected_degradation_mode=data.get("expected_degradation_mode", "graceful"),
        )

    @classmethod
    def from_json(cls, text: str) -> FaultProfile:
        return cls.from_dict(json.loads(text))


# ---------------------------------------------------------------------------
# Built-in profiles
# ---------------------------------------------------------------------------

BUILTIN_PROFILES: dict[str, FaultProfile] = {
    "a2a_timeout_on_send": FaultProfile(
        profile_id="a2a_timeout_on_send",
        seed=42,
        description="Timeout on first call to /a2a/message/send",
        fault_events=[
            FaultEvent(
                call_index=0,
                fault_type=FaultType.TIMEOUT,
                target_service="registry",
                target_endpoint="/a2a/message/send",
                duration_ms=5000,
            ),
        ],
        max_retry_budget=3,
        expected_degradation_mode="graceful",
    ),
    "catalog_500_on_search": FaultProfile(
        profile_id="catalog_500_on_search",
        seed=42,
        description="HTTP 500 on first call to catalog /books",
        fault_events=[
            FaultEvent(
                call_index=0,
                fault_type=FaultType.HTTP_500,
                target_service="catalog",
                target_endpoint="/books",
            ),
        ],
        max_retry_budget=3,
        expected_degradation_mode="graceful",
    ),
    "registry_intermittent": FaultProfile(
        profile_id="registry_intermittent",
        seed=42,
        description="Intermittent outage on 1st and 3rd calls to registry",
        fault_events=[
            FaultEvent(
                call_index=0,
                fault_type=FaultType.INTERMITTENT_OUTAGE,
                target_service="registry",
                target_endpoint="/a2a/message/send",
            ),
            FaultEvent(
                call_index=2,
                fault_type=FaultType.INTERMITTENT_OUTAGE,
                target_service="registry",
                target_endpoint="/a2a/message/send",
            ),
        ],
        max_retry_budget=5,
        expected_degradation_mode="retry",
    ),
    "malformed_a2a_response": FaultProfile(
        profile_id="malformed_a2a_response",
        seed=42,
        description="Malformed JSON response from registry relay",
        fault_events=[
            FaultEvent(
                call_index=0,
                fault_type=FaultType.MALFORMED_JSON,
                target_service="registry",
                target_endpoint="/a2a/message/send",
            ),
        ],
        max_retry_budget=3,
        expected_degradation_mode="graceful",
    ),
}


def load_profile(profile_id: str, seed: int | None = None) -> FaultProfile:
    """Load a built-in profile, optionally overriding its seed."""
    if profile_id not in BUILTIN_PROFILES:
        raise KeyError(f"Unknown chaos profile: {profile_id!r}")
    profile = BUILTIN_PROFILES[profile_id]
    if seed is not None:
        return FaultProfile(
            profile_id=profile.profile_id,
            seed=seed,
            description=profile.description,
            fault_events=list(profile.fault_events),
            max_retry_budget=profile.max_retry_budget,
            expected_degradation_mode=profile.expected_degradation_mode,
        )
    return profile
