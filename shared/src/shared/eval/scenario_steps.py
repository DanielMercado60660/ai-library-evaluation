"""Scenario step schema helpers for benchmark manifests and trace events."""

from __future__ import annotations

from typing import Any


def build_default_scenario_steps(
    *,
    expected_steps: int,
    policy_checks: int,
    tool_calls_total: int,
) -> list[dict[str, Any]]:
    """Create a deterministic, evaluator-friendly step plan for a scenario.

    The step count is aligned to ``expected_steps`` when possible while keeping
    a stable structure suitable for UI rendering and trace streaming.
    """
    expected = max(int(expected_steps or 0), 1)
    policy_count = max(int(policy_checks or 0), 0)
    tool_count = max(int(tool_calls_total or 0), 0)

    if expected == 1:
        return [
            {
                "step_id": "final_response",
                "order": 1,
                "title": "Finalize Response",
                "description": "Return benchmark outcome and completion status.",
                "phase": "outcome",
                "expected_signal": "scenario result recorded",
            }
        ]

    steps: list[dict[str, Any]] = [
        {
            "step_id": "intake_request",
            "order": 0,
            "title": "Intake Prompt",
            "description": "Capture scenario intent and normalize inputs.",
            "phase": "intake",
            "expected_signal": "scenario context initialized",
        }
    ]

    middle: list[dict[str, Any]] = []

    if tool_count > 0:
        middle.append(
            {
                "step_id": "tool_execution",
                "order": 0,
                "title": "Execute Tool Calls",
                "description": f"Run up to {tool_count} catalog/circulation/ILL tool call(s).",
                "phase": "tools",
                "expected_signal": "tool interactions captured",
            }
        )

    if policy_count > 0:
        middle.append(
            {
                "step_id": "policy_guardrails",
                "order": 0,
                "title": "Apply Policy Guards",
                "description": f"Validate {policy_count} policy and safety rule(s).",
                "phase": "policy",
                "expected_signal": "policy checks evaluated",
            }
        )

    middle.append(
        {
            "step_id": "verification",
            "order": 0,
            "title": "Verify Output",
            "description": "Confirm completeness, factuality, and state integrity.",
            "phase": "verification",
            "expected_signal": "verification assertions computed",
        }
    )

    target_middle_count = max(expected - 2, 0)
    synthesis_idx = 0
    while len(middle) < target_middle_count:
        synthesis_idx += 1
        middle.insert(
            max(len(middle) - 1, 0),
            {
                "step_id": f"context_synthesis_{synthesis_idx}",
                "order": 0,
                "title": "Synthesize Context",
                "description": "Consolidate intermediate findings before final output.",
                "phase": "analysis",
                "expected_signal": "intermediate context snapshot recorded",
            },
        )

    steps.extend(middle[:target_middle_count])
    steps.append(
        {
            "step_id": "final_response",
            "order": 0,
            "title": "Finalize Response",
            "description": "Return benchmark outcome and completion status.",
            "phase": "outcome",
            "expected_signal": "scenario result recorded",
        }
    )

    for index, step in enumerate(steps, start=1):
        step["order"] = index
    return steps


def derive_step_outcomes(
    *,
    step_count: int,
    scenario_status: str,
) -> list[str]:
    """Project step-level outcomes from a scenario-level status."""
    if step_count <= 0:
        return []

    normalized = (scenario_status or "").strip().lower()
    if normalized in {"passed", "pass"}:
        return ["pass"] * step_count
    if normalized in {"skipped", "skip", "xfail", "xfailed"}:
        return ["skipped"] * step_count

    # Failed/error scenarios are modeled as failing at the final step.
    outcomes = ["pass"] * step_count
    outcomes[-1] = "fail"
    return outcomes
