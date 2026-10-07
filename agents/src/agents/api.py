"""FastAPI application for the AI Library agent service."""

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared.auth import ServiceAuthMiddleware
from shared.observability import RequestCorrelationMiddleware
from shared.eval.scenario_steps import build_default_scenario_steps
from agents.benchmark_api_models import (
    BenchmarkModelCatalogResponse,
    BenchmarkModelOption,
    LeaderboardResponse,
    RunComparisonRequest,
    RunComparisonResponse,
    RunCreateRequest,
    RunCreateResponse,
    RunListResponse,
    RunStatus,
    ScenarioCatalogResponse,
)
from agents.benchmark_comparison import (
    build_comparison,
    build_leaderboard,
    is_completed_run,
    load_report,
)
from agents.config import MODEL_NAME
from agents.benchmark_orchestrator import BenchmarkOrchestrator
from agents.chat import session_manager

ARTIFACTS_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_MANIFEST_PATH = REPO_ROOT / "tests" / "scenarios" / "scenario_manifest.json"
SCENARIO_SCRIPTS_PATH = REPO_ROOT / "tests" / "scenarios" / "scenario_chat_scripts.json"
MODEL_CATALOG_ENV = "BENCHMARK_MODELS"
MODEL_CATALOG_FALLBACK = (
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
)

orchestrator = BenchmarkOrchestrator(ARTIFACTS_DIR)


def _infer_model_family(model_name: str) -> str:
    lowered = model_name.strip().lower()
    if lowered.startswith("gemini"):
        return "gemini"
    if not lowered:
        return "unknown"
    return lowered.split("-", 1)[0]


def _load_model_catalog() -> BenchmarkModelCatalogResponse:
    default_model = (MODEL_NAME or "").strip() or "gemini-3-flash-preview"
    configured = [
        candidate.strip()
        for candidate in os.getenv(MODEL_CATALOG_ENV, "").split(",")
        if candidate.strip()
    ]

    ordered: list[str] = []
    seen: set[str] = set()

    for model in [default_model, *configured, *MODEL_CATALOG_FALLBACK]:
        if model in seen:
            continue
        seen.add(model)
        ordered.append(model)

    return BenchmarkModelCatalogResponse(
        default_model=default_model,
        models=[
            BenchmarkModelOption(
                model_name=model,
                model_family=_infer_model_family(model),
                is_default=model == default_model,
            )
            for model in ordered
        ],
    )


def _load_manifest_scenario_ids() -> set[str]:
    """Load known scenario ids from the benchmark manifest."""
    if not SCENARIO_MANIFEST_PATH.exists():
        return set()

    try:
        payload = json.loads(SCENARIO_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return set()

    ids: set[str] = set()
    for raw in payload.get("scenarios", []):
        scenario_id = str(raw.get("id", "") or "").strip()
        if scenario_id:
            ids.add(scenario_id)
    return ids


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    class ActivePatron(BaseModel):
        """Identity context for the currently active evaluator patron."""

        id: str
        name: str | None = None
        role: Literal["patron", "staff"] | None = None

    message: str
    session_id: Optional[str] = None
    active_patron: ActivePatron | None = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    response: str
    session_id: str
    bound_patron_id: str | None = None
    session_rebound: bool = False


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    service: str
    version: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="AI Library - Agent Service",
    description="Chat with the AI Librarian",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service trust middleware (expanded public paths for agent-facing endpoints)
app.add_middleware(
    ServiceAuthMiddleware,
    public_prefixes=(
        "/health", "/docs", "/openapi.json", "/redoc",
        "/chat", "/sessions", "/benchmark",
    ),
)

# Request correlation (outermost — added last, runs first)
app.add_middleware(RequestCorrelationMiddleware)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        service="agents",
        version="0.1.0",
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat with the AI librarian.

    Send a message and receive a response. Optionally include a session_id
    to continue an existing conversation.
    """
    try:
        requested_patron_id = None
        requested_patron_name = None
        requested_patron_role = None
        if request.active_patron:
            requested_patron_id = request.active_patron.id.strip() or None
            requested_patron_name = request.active_patron.name
            requested_patron_role = request.active_patron.role

        session, session_rebound = await session_manager.resolve_session_for_request(
            session_id=request.session_id,
            patron_id=requested_patron_id,
            patron_name=requested_patron_name,
            patron_role=requested_patron_role,
        )

        # Process the message
        response = await session.send_message(request.message)

        # Persist session state (conversation history, patron context)
        await session_manager.save_session(session)

        return ChatResponse(
            response=response,
            session_id=session.session_id,
            bound_patron_id=session.bound_patron_id,
            session_rebound=session_rebound,
        )
    except Exception as e:
        # Log the error in production
        raise HTTPException(
            status_code=500,
            detail=f"Error processing message: {str(e)}"
        )


@app.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    """End a chat session."""
    if await session_manager.end_session_async(session_id):
        return {"status": "session ended"}
    raise HTTPException(status_code=404, detail="Session not found")


# --- Benchmark Run Control Plane (v1.5) ---


@app.get("/benchmark/report")
async def get_benchmark_report():
    """Serve the latest benchmark report JSON.

    Compatibility alias: resolves to the latest successful run's report
    when available, falls back to legacy flat artifacts/benchmark-report.json.
    """
    latest = orchestrator.latest_successful()
    if latest and latest.report_path:
        report_path = Path(latest.report_path)
        if report_path.exists():
            data = json.loads(report_path.read_text())
            return JSONResponse(content=data)

    report_path = ARTIFACTS_DIR / "benchmark-report.json"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="No benchmark report found")
    data = json.loads(report_path.read_text())
    return JSONResponse(content=data)


@app.get("/benchmark/scenarios", response_model=ScenarioCatalogResponse)
async def get_benchmark_scenarios():
    """Serve benchmark scenario manifest and optional chat scripts."""
    if not SCENARIO_MANIFEST_PATH.exists():
        raise HTTPException(status_code=404, detail="Scenario manifest not found")

    payload = json.loads(SCENARIO_MANIFEST_PATH.read_text(encoding="utf-8"))
    scripts: dict[str, list[str]] = {}
    if SCENARIO_SCRIPTS_PATH.exists():
        script_payload = json.loads(SCENARIO_SCRIPTS_PATH.read_text(encoding="utf-8"))
        scripts = script_payload.get("scripts", {})

    raw_scenarios = payload.get("scenarios", [])
    scenarios: list[dict[str, object]] = []
    for raw in raw_scenarios:
        scenario = dict(raw)
        existing_steps = scenario.get("steps")
        if not isinstance(existing_steps, list) or not existing_steps:
            scenario["steps"] = build_default_scenario_steps(
                expected_steps=int(scenario.get("expected_steps", 1) or 1),
                policy_checks=int(scenario.get("policy_checks", 0) or 0),
                tool_calls_total=int(scenario.get("tool_calls_total", 0) or 0),
            )
        scenarios.append(scenario)

    return ScenarioCatalogResponse(
        manifest_version=str(payload.get("manifest_version", "unknown")),
        suite=str(payload.get("suite", "")),
        generated_at=str(payload.get("generated_at", "")),
        scenarios=scenarios,
        scripts=scripts,
    )


@app.get("/benchmark/models", response_model=BenchmarkModelCatalogResponse)
async def get_benchmark_models():
    """Serve selectable benchmark model variants for run configuration."""
    return _load_model_catalog()


@app.post("/benchmark/runs", response_model=RunCreateResponse, status_code=202)
async def create_benchmark_run(request: RunCreateRequest):
    """Create and launch a new benchmark run.

    Returns immediately with run_id. The benchmark executes
    asynchronously. Poll GET /benchmark/runs/{run_id} for status.
    """
    if request.run_mode == "eval" and request.suite != "scenarios" and not request.scenario_ids:
        raise HTTPException(
            status_code=400,
            detail="run_mode='eval' requires suite='scenarios' or explicit scenario_ids",
        )

    if request.run_mode == "benchmark" and request.benchmark_config:
        from agents.benchmark_config import BenchmarkConfig
        from pydantic import ValidationError

        try:
            BenchmarkConfig.model_validate(request.benchmark_config)
        except ValidationError as exc:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid benchmark_config: {exc}",
            )

    if request.scenario_ids:
        if request.suite != "scenarios":
            raise HTTPException(
                status_code=400,
                detail="scenario_ids are only supported when suite='scenarios'",
            )

        deduped_ids: list[str] = []
        seen: set[str] = set()
        for value in request.scenario_ids:
            scenario_id = (value or "").strip()
            if not scenario_id or scenario_id in seen:
                continue
            seen.add(scenario_id)
            deduped_ids.append(scenario_id)

        if not deduped_ids:
            raise HTTPException(
                status_code=400,
                detail="scenario_ids must contain at least one non-empty scenario id",
            )

        known_ids = _load_manifest_scenario_ids()
        if not known_ids:
            raise HTTPException(
                status_code=400,
                detail="Scenario manifest unavailable; cannot validate scenario_ids",
            )

        unknown = [scenario_id for scenario_id in deduped_ids if scenario_id not in known_ids]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scenario id(s): {', '.join(unknown)}",
            )

        request = request.model_copy(update={"scenario_ids": deduped_ids})

    request = request.model_copy(
        update={
            "trigger_source": (request.trigger_source or "manual").strip() or "manual",
            "actor_patron_id": (request.actor_patron_id or "").strip() or None,
        },
    )

    metadata = orchestrator.create_run(request)
    await orchestrator.launch_run(metadata.run_id, request)
    return RunCreateResponse(
        run_id=metadata.run_id,
        status=metadata.status,
        run_mode=metadata.run_mode,
        artifact_dir=metadata.artifact_dir,
        model_name=metadata.model_name,
        model_family=metadata.model_family,
        scenario_ids=metadata.scenario_ids,
        trigger_source=metadata.trigger_source,
        actor_patron_id=metadata.actor_patron_id,
    )


@app.get("/benchmark/runs", response_model=RunListResponse)
async def list_benchmark_runs():
    """List all benchmark runs with metadata."""
    runs = orchestrator.list_runs()
    return RunListResponse(runs=runs, total=len(runs))


@app.get("/benchmark/runs/{run_id}")
async def get_benchmark_run(run_id: str):
    """Get metadata for a specific benchmark run."""
    metadata = orchestrator.get_run(run_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return metadata.model_dump(mode="json")


@app.get("/benchmark/runs/{run_id}/report")
async def get_benchmark_run_report(run_id: str):
    """Get the benchmark report for a specific run."""
    metadata = orchestrator.get_run(run_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if metadata.report_path is None:
        raise HTTPException(
            status_code=404, detail=f"Run '{run_id}' has no report yet"
        )
    report_path = Path(metadata.report_path)
    if not report_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Report file not found for run '{run_id}'",
        )
    data = json.loads(report_path.read_text())
    return JSONResponse(content=data)


@app.get("/benchmark/runs/{run_id}/trace")
async def get_benchmark_run_trace(run_id: str):
    """Get the trace JSONL for a specific run."""
    metadata = orchestrator.get_run(run_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    trace_path = (
        Path(metadata.trace_path)
        if metadata.trace_path
        else Path(metadata.artifact_dir) / "benchmark-trace.jsonl"
    )
    if not trace_path.exists():
        if metadata.status in {RunStatus.QUEUED, RunStatus.RUNNING}:
            return JSONResponse(content=[])
        raise HTTPException(
            status_code=404,
            detail=f"Trace file not found for run '{run_id}'",
        )

    lines = trace_path.read_text().splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    return JSONResponse(content=events)


@app.get("/benchmark/runs/{run_id}/artifacts")
async def list_benchmark_run_artifacts(run_id: str):
    """List all artifact files for a specific run."""
    metadata = orchestrator.get_run(run_id)
    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return JSONResponse(
        content={
            "run_id": run_id,
            "artifact_dir": metadata.artifact_dir,
            "artifacts": metadata.artifact_paths,
        }
    )


@app.post("/benchmark/compare", response_model=RunComparisonResponse)
async def compare_benchmark_runs(request: RunComparisonRequest):
    """Compare completed benchmark runs using deterministic summary deltas."""
    run_reports: list[tuple] = []
    seen: set[str] = set()
    deduped_run_ids: list[str] = []
    for run_id in request.run_ids:
        if run_id in seen:
            continue
        seen.add(run_id)
        deduped_run_ids.append(run_id)

    if len(deduped_run_ids) < 2 or len(deduped_run_ids) > 5:
        raise HTTPException(status_code=400, detail="run_ids must contain 2 to 5 unique values")

    for run_id in deduped_run_ids:
        metadata = orchestrator.get_run(run_id)
        if metadata is None:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
        if request.suite and metadata.suite != request.suite:
            raise HTTPException(
                status_code=400,
                detail=f"Run '{run_id}' does not match requested suite '{request.suite}'",
            )
        if not is_completed_run(metadata):
            raise HTTPException(status_code=400, detail=f"Run '{run_id}' is not completed")
        report = load_report(metadata)
        if report is None:
            raise HTTPException(status_code=404, detail=f"Run '{run_id}' report not found")
        run_reports.append((metadata, report))

    return build_comparison(run_reports)


@app.get("/benchmark/leaderboard", response_model=LeaderboardResponse)
async def get_benchmark_leaderboard(
    suite: str | None = None,
    limit: int = Query(default=20, ge=1, le=200),
    min_runs: int = Query(default=1, ge=1, le=50),
):
    """Return deterministic model leaderboard aggregated from completed runs."""
    run_reports: list[tuple] = []
    for metadata in orchestrator.list_runs():
        if not is_completed_run(metadata):
            continue
        if suite and metadata.suite != suite:
            continue
        report = load_report(metadata)
        if report is None:
            continue
        run_reports.append((metadata, report))

    return build_leaderboard(
        run_reports,
        suite=suite,
        min_runs=min_runs,
        limit=limit,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
