"""Pydantic models for benchmark run control plane and v2.1 comparison APIs."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    """Lifecycle states for a benchmark run."""

    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"


class RunCreateRequest(BaseModel):
    """Request body for POST /benchmark/runs."""

    suite: str = "smoke"
    include_adk: bool = False
    no_forensic: bool = False
    chaos_profile: Optional[str] = None
    model_name: Optional[str] = None
    scenario_ids: Optional[list[str]] = None
    run_mode: str = "pytest"
    trigger_source: Optional[str] = "manual"
    actor_patron_id: Optional[str] = None
    benchmark_config: Optional[dict[str, Any]] = None


class RunMetadata(BaseModel):
    """Persisted metadata for a single benchmark run."""

    run_id: str
    suite: str
    status: RunStatus
    run_mode: str = "pytest"
    model_name: str = "unknown"
    model_family: str = "gemini"
    started_at: datetime
    completed_at: Optional[datetime] = None
    artifact_dir: str
    report_path: Optional[str] = None
    trace_path: Optional[str] = None
    artifact_paths: list[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    scenario_ids: list[str] = Field(default_factory=list)
    trigger_source: str = "manual"
    actor_patron_id: Optional[str] = None


class RunCreateResponse(BaseModel):
    """Response from POST /benchmark/runs."""

    run_id: str
    status: RunStatus
    run_mode: str = "pytest"
    artifact_dir: str
    model_name: str
    model_family: str = "gemini"
    scenario_ids: list[str] = Field(default_factory=list)
    trigger_source: str = "manual"
    actor_patron_id: Optional[str] = None


class RunListResponse(BaseModel):
    """Response from GET /benchmark/runs."""

    runs: list[RunMetadata]
    total: int


class RunIndex(BaseModel):
    """Root schema for artifacts/runs/index.json."""

    schema_version: str = "1.5"
    runs: list[RunMetadata] = Field(default_factory=list)


class ScenarioStepDefinition(BaseModel):
    """Evaluator-visible step definition for a benchmark scenario."""

    step_id: str
    order: int
    title: str
    description: str
    phase: str
    expected_signal: str


class ScenarioManifestEntry(BaseModel):
    """Scenario metadata entry loaded from the benchmark manifest."""

    id: str
    nodeid_pattern: str
    tier: int
    expected_steps: int
    policy_checks: int
    tool_calls_total: int
    taxonomy_hint: str
    steps: list[ScenarioStepDefinition] = Field(default_factory=list)


class ScenarioCatalogResponse(BaseModel):
    """Response from GET /benchmark/scenarios."""

    manifest_version: str
    suite: str
    generated_at: str
    scenarios: list[ScenarioManifestEntry]
    scripts: dict[str, list[str]] = Field(default_factory=dict)


class BenchmarkModelOption(BaseModel):
    """Selectable benchmark model option."""

    model_name: str
    model_family: str = "gemini"
    is_default: bool = False


class BenchmarkModelCatalogResponse(BaseModel):
    """Response from GET /benchmark/models."""

    default_model: str
    models: list[BenchmarkModelOption]


class RunComparisonRequest(BaseModel):
    """Request body for POST /benchmark/compare."""

    run_ids: list[str] = Field(min_length=2, max_length=5)
    suite: Optional[str] = None


class RunScoreSnapshot(BaseModel):
    """Aggregate metrics for one comparable run."""

    run_id: str
    suite: str
    status: RunStatus
    model_name: str
    model_family: str
    total_scenarios: int
    completion_rate_percent: float
    policy_compliance_percent: float
    tool_precision_percent: float
    hallucinations: int
    composite_score: float


class RunMetricDelta(BaseModel):
    """Run-level delta against baseline."""

    run_id: str
    baseline_run_id: str
    composite_score_delta: float
    completion_rate_delta: float
    policy_compliance_delta: float
    tool_precision_delta: float
    hallucinations_delta: float


class TierDelta(BaseModel):
    """Tier-level metric delta against baseline."""

    run_id: str
    baseline_run_id: str
    tier: int
    completion_rate_delta: float
    policy_compliance_delta: float
    tool_precision_delta: float
    hallucinations_delta: float


class ScenarioDelta(BaseModel):
    """Scenario-level metric delta against baseline."""

    run_id: str
    baseline_run_id: str
    scenario_id: str
    completion_delta: float
    policy_compliance_delta: float
    tool_precision_delta: float
    hallucinations_delta: int


class RunComparisonResponse(BaseModel):
    """Response from POST /benchmark/compare."""

    baseline_run_id: str
    ranked_run_ids: list[str]
    runs: list[RunScoreSnapshot]
    run_deltas: list[RunMetricDelta]
    tier_deltas: list[TierDelta]
    scenario_deltas: list[ScenarioDelta]


class LeaderboardRow(BaseModel):
    """One row in the benchmark leaderboard."""

    rank: int
    model_name: str
    model_family: str
    run_count: int
    avg_composite_score: float
    avg_completion_rate: float
    avg_policy_compliance: float
    avg_tool_precision: float
    avg_hallucinations: float


class LeaderboardResponse(BaseModel):
    """Response from GET /benchmark/leaderboard."""

    suite: Optional[str] = None
    min_runs: int
    total_models: int
    rows: list[LeaderboardRow]
