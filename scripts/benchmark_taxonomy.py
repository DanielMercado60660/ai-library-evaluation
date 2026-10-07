"""Failure taxonomy mapping for benchmark run artifacts."""

from __future__ import annotations

import re
from typing import Iterable


TAXONOMY = {
    "tool_misuse": [
        r"tool",
        r"parameter",
        r"invalid request",
        r"400",
    ],
    "state_drift": [
        r"status",
        r"state",
        r"transition",
        r"out of order",
    ],
    "policy_break": [
        r"blocked",
        r"limit",
        r"denied",
        r"policy",
        r"compliance",
    ],
    "hallucination": [
        r"hallucination",
        r"fabricat",
        r"synthetic",
        r"real-world",
    ],
    "timeout": [
        r"timeout",
        r"timed out",
        r"unavailable",
        r"connection",
    ],
    "content_fabrication": [
        r"fabricat",
        r"null.?content",
        r"invented",
        r"made up",
        r"full text",
        r"passage",
    ],
    "pii_leakage": [
        r"canary",
        r"pii",
        r"leak",
        r"personal information",
        r"patron data",
        r"patron.?email",
        r"patron.?phone",
    ],
    "resilience_failure": [
        r"resilience",
        r"chaos",
        r"fault.?inject",
        r"recovery.?fail",
        r"degraded",
    ],
    "timeout_exhaustion": [
        r"retry.?budget",
        r"max.?retries",
        r"exhausted",
        r"circuit.?open",
    ],
}


def classify_failure(
    nodeid: str,
    message: str,
    taxonomy_hint: str | None = None,
    markers: Iterable[str] | None = None,
) -> str:
    """Map test failure to taxonomy bucket using explicit hints then patterns."""
    lower = (message or "").lower()
    node = nodeid.lower()
    marker_values = [m.lower() for m in (markers or [])]

    if taxonomy_hint in TAXONOMY:
        return taxonomy_hint

    # Explicit taxonomy hints can be embedded as "taxonomy::<category>".
    marker = re.search(r"taxonomy::([a-z_]+)", lower)
    if marker:
        category = marker.group(1)
        if category in TAXONOMY:
            return category
    for marker_value in marker_values:
        marker_match = re.search(r"taxonomy::([a-z_]+)", marker_value)
        if marker_match:
            category = marker_match.group(1)
            if category in TAXONOMY:
                return category

    for category, patterns in TAXONOMY.items():
        if any(re.search(pat, lower) for pat in patterns):
            return category

    # Node-based fallback hints.
    if "mcp" in node or "tool" in node:
        return "tool_misuse"
    if "state" in node or "lifecycle" in node:
        return "state_drift"
    if "guardrail" in node:
        return "hallucination"

    return "unknown"
