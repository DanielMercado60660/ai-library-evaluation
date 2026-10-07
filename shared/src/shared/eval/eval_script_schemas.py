"""Pydantic models for structured eval scripts used by the evaluation pipeline.

Eval scripts define multi-turn prescripted conversations with per-step
assertions. The EvalScriptExecutor replays these scripts against the live
``/chat`` endpoint and captures pass/fail results for each assertion.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class StepAssertion(BaseModel):
    """A state assertion checked after an eval step completes.

    The executor issues an HTTP GET to ``{service_base_url}{endpoint}``
    and evaluates ``field_path`` against ``expected_value``.
    """

    service: Literal["catalog", "circulation", "ill", "registry"]
    endpoint: str = Field(
        description="HTTP path appended to the service base URL, e.g. '/patrons/patron-001/fines'",
    )
    field_path: str = Field(
        description="Dot-separated path into the JSON response, e.g. 'total' or 'items.0.status'",
    )
    expected_value: Any = Field(
        description="Expected value at field_path. Compared with == after type coercion.",
    )
    description: str = ""


class EvalStep(BaseModel):
    """One turn in a prescripted eval conversation."""

    step_id: str
    order: int
    patron_message: str = Field(
        description="The message sent to POST /chat as the patron.",
    )
    expected_tool_calls: list[str] = Field(
        default_factory=list,
        description="Tool names the agent should invoke during this step (order-independent).",
    )
    response_must_contain: list[str] = Field(
        default_factory=list,
        description="Substrings that MUST appear in the agent response (case-insensitive).",
    )
    response_must_not_contain: list[str] = Field(
        default_factory=list,
        description="Substrings that MUST NOT appear in the agent response (case-insensitive).",
    )
    state_assertions: list[StepAssertion] = Field(
        default_factory=list,
        description="Service state checks to run after the step.",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Maximum wall-clock time for this step before it is marked as timed out.",
    )


class EvalScript(BaseModel):
    """Complete eval script for one scenario.

    Maps 1-to-1 with a scenario_manifest entry via ``scenario_id``.
    """

    scenario_id: str
    patron_id: str
    patron_name: str = ""
    patron_role: Literal["patron", "staff"] = "patron"
    setup_notes: str = ""
    skip_live_eval: bool = False
    skip_reason: str = ""
    steps: list[EvalStep] = Field(default_factory=list)


class EvalScriptCatalog(BaseModel):
    """Root container for all eval scripts, loaded from JSON."""

    schema_version: str = "1.0"
    scripts: dict[str, EvalScript] = Field(
        default_factory=dict,
        description="Mapping from scenario_id to its EvalScript.",
    )
