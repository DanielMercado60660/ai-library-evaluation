"""Async benchmark orchestration for run control plane (v1.5)."""

import asyncio
import json
import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from agents.benchmark_api_models import RunCreateRequest, RunMetadata, RunStatus
from agents.config import MODEL_NAME
from agents.run_index import RunIndexManager

from shared.eval.eval_script_schemas import EvalScriptCatalog
from shared.eval.trace_schemas import TraceEventType
from shared.eval.trace_writer import TraceWriter

logger = logging.getLogger(__name__)

# Resolve repo root relative to this file (agents/src/agents/ → repo root).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _infer_model_family(model_name: str) -> str:
    """Infer a model family label for display and grouping."""
    lowered = model_name.strip().lower()
    if lowered.startswith("gemini"):
        return "gemini"
    if not lowered:
        return "unknown"
    return lowered.split("-", 1)[0]


class BenchmarkOrchestrator:
    """Manages benchmark run lifecycle and async execution."""

    def __init__(self, artifacts_dir: Path) -> None:
        self._artifacts_dir = artifacts_dir
        self._index = RunIndexManager(artifacts_dir)
        self._active_tasks: dict[str, asyncio.Task[None]] = {}

    def create_run(self, request: RunCreateRequest) -> RunMetadata:
        """Create a new run entry with status=queued.

        Generates a run_id, creates the run artifact directory,
        and adds the entry to the run index.
        """
        run_id = f"run-{uuid4().hex[:16]}"
        artifact_dir = self._index.run_artifact_dir(run_id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        trace_path = artifact_dir / "benchmark-trace.jsonl"
        selected_model = (request.model_name or MODEL_NAME).strip() or MODEL_NAME
        scenario_ids = list(request.scenario_ids or [])
        trigger_source = (request.trigger_source or "manual").strip() or "manual"
        actor_patron_id = (request.actor_patron_id or "").strip() or None

        metadata = RunMetadata(
            run_id=run_id,
            suite=request.suite,
            status=RunStatus.QUEUED,
            run_mode=request.run_mode or "pytest",
            model_name=selected_model,
            model_family=_infer_model_family(selected_model),
            started_at=datetime.now(timezone.utc),
            artifact_dir=str(artifact_dir),
            trace_path=str(trace_path),
            scenario_ids=scenario_ids,
            trigger_source=trigger_source,
            actor_patron_id=actor_patron_id,
        )
        self._index.add_run(metadata)
        return metadata

    async def launch_run(
        self, run_id: str, request: RunCreateRequest
    ) -> None:
        """Launch benchmark execution as a background asyncio task."""
        task = asyncio.create_task(self._execute_run(run_id, request))
        self._active_tasks[run_id] = task

    async def _execute_run(
        self, run_id: str, request: RunCreateRequest
    ) -> None:
        """Route execution: eval, benchmark, or pytest mode."""
        self._index.update_run(run_id, status=RunStatus.RUNNING)

        mode = request.run_mode or "pytest"
        if mode == "eval":
            await self._execute_eval_run(run_id, request)
        elif mode == "benchmark":
            await self._execute_benchmark_run(run_id, request)
        else:
            await self._execute_pytest_run(run_id, request)

    async def _execute_eval_run(
        self, run_id: str, request: RunCreateRequest
    ) -> None:
        """Execute eval scripts against the live /chat endpoint."""
        from agents.eval_executor import EvalScriptExecutor
        from agents.eval_report import build_eval_report, build_eval_markdown
        from agents.eval_seeder import EvalDatabaseSeeder

        metadata = self._index.get_run(run_id)
        if metadata is None:
            return
        artifact_dir = Path(metadata.artifact_dir)

        trace_path = artifact_dir / "benchmark-trace.jsonl"
        report_path = artifact_dir / "benchmark-report.json"
        md_path = artifact_dir / "benchmark-report.md"

        trace_writer = TraceWriter(trace_path, run_id=run_id)

        trace_writer.emit(
            TraceEventType.BENCHMARK_RUN_START,
            source="orchestrator",
            payload={"run_mode": "eval", "suite": request.suite},
        )

        try:
            # Load eval scripts
            script_path = _REPO_ROOT / "tests" / "scenarios" / "scenario_eval_scripts.json"
            if not script_path.exists():
                raise FileNotFoundError(f"Eval scripts not found: {script_path}")

            catalog = EvalScriptCatalog.model_validate_json(
                script_path.read_text(encoding="utf-8")
            )

            # Filter to requested scenarios
            requested_ids = set(metadata.scenario_ids) if metadata.scenario_ids else None
            scripts_to_run = {
                sid: script
                for sid, script in catalog.scripts.items()
                if (requested_ids is None or sid in requested_ids)
                and not script.skip_live_eval
            }

            # Seed databases
            seeder = EvalDatabaseSeeder()
            try:
                await seeder.reset_and_seed_all()
            except Exception as seed_err:
                logger.warning("Seed failed (continuing): %s", seed_err)

            # Execute scenarios
            executor = EvalScriptExecutor(
                trace_writer=trace_writer,
            )

            scenario_results = []
            for sid, script in scripts_to_run.items():
                trace_writer.emit(
                    TraceEventType.SCENARIO_START,
                    source="orchestrator",
                    scenario_id=sid,
                    payload={"patron_id": script.patron_id},
                )

                sr = await executor.execute_scenario(sid, script, run_id)
                scenario_results.append(sr)

                trace_writer.emit(
                    TraceEventType.SCENARIO_END,
                    source="orchestrator",
                    scenario_id=sid,
                    payload={
                        "passed": sr.passed,
                        "total_assertions": sr.total_assertions,
                        "passed_assertions": sr.passed_assertions,
                        "duration_ms": sr.duration_ms,
                    },
                )

            # Build report
            report = build_eval_report(
                run_id=run_id,
                scenario_results=scenario_results,
                model_name=metadata.model_name,
                suite=request.suite,
            )

            trace_writer.emit(
                TraceEventType.BENCHMARK_RUN_END,
                source="orchestrator",
                payload={
                    "total_scenarios": report["summary"]["total"],
                    "passed": report["summary"]["passed"],
                    "failed": report["summary"]["failed"],
                },
            )

            report["trace_summary"] = trace_writer.summary().model_dump(mode="json")

            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            md_path.write_text(build_eval_markdown(report), encoding="utf-8")

            all_passed = report["summary"]["failed"] == 0
            final_status = RunStatus.PASSED if all_passed else RunStatus.FAILED

            artifact_paths = [
                str(p.relative_to(artifact_dir))
                for p in artifact_dir.rglob("*")
                if p.is_file()
            ]

            self._index.update_run(
                run_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc),
                report_path=str(report_path),
                trace_path=str(trace_path),
                artifact_paths=artifact_paths,
            )

        except Exception as exc:
            logger.exception("Eval run %s failed", run_id)
            self._index.update_run(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
        finally:
            self._active_tasks.pop(run_id, None)

    async def _execute_benchmark_run(
        self, run_id: str, request: RunCreateRequest
    ) -> None:
        """Execute open-ended benchmark interactions against live /chat."""
        import time as _time

        from agents.benchmark_config import BenchmarkConfig
        from agents.benchmark_report_builder import (
            build_benchmark_report,
            build_benchmark_markdown,
        )
        from agents.benchmark_session_executor import BenchmarkSessionExecutor
        from agents.eval_seeder import EvalDatabaseSeeder
        from agents.patron_request_generator import PatronRequestGenerator

        metadata = self._index.get_run(run_id)
        if metadata is None:
            return
        artifact_dir = Path(metadata.artifact_dir)

        trace_path = artifact_dir / "benchmark-trace.jsonl"
        report_path = artifact_dir / "benchmark-report.json"
        md_path = artifact_dir / "benchmark-report.md"

        trace_writer = TraceWriter(trace_path, run_id=run_id)

        # Parse config (use defaults if not provided)
        raw_config = request.benchmark_config or {}
        config = BenchmarkConfig.model_validate(raw_config)

        trace_writer.emit(
            TraceEventType.BENCHMARK_RUN_START,
            source="orchestrator",
            payload={
                "run_mode": "benchmark",
                "suite": request.suite,
                "interaction_count": config.interaction_count,
                "time_budget_seconds": config.time_budget_seconds,
            },
        )

        wall_start = _time.monotonic()

        try:
            # Seed databases if configured
            if config.seed_before_run:
                seeder = EvalDatabaseSeeder()
                try:
                    await seeder.reset_and_seed_all()
                except Exception as seed_err:
                    logger.warning("Benchmark seed failed (continuing): %s", seed_err)

            # Generate interactions
            generator = PatronRequestGenerator(config)
            interactions = generator.generate()

            # Collect known book data for hallucination detection
            known_titles = [
                b.get("title", "") for b in generator._books
            ]
            known_authors = [
                a.get("name", "") for a in generator._authors
            ]

            # Execute
            executor = BenchmarkSessionExecutor(
                config=config,
                trace_writer=trace_writer,
                known_book_titles=known_titles,
                known_authors=known_authors,
            )
            results, metrics = await executor.execute(interactions)

            wall_seconds = _time.monotonic() - wall_start

            # Build report
            report = build_benchmark_report(
                run_id=run_id,
                results=results,
                metrics=metrics,
                config=config,
                model_name=metadata.model_name,
                suite=request.suite,
                wall_clock_seconds=wall_seconds,
            )

            trace_writer.emit(
                TraceEventType.BENCHMARK_RUN_END,
                source="orchestrator",
                payload={
                    "total_interactions": metrics.total_interactions,
                    "completed": metrics.completed,
                    "errored": metrics.errored,
                    "wall_clock_seconds": round(wall_seconds, 1),
                },
            )

            report["trace_summary"] = trace_writer.summary().model_dump(mode="json")

            report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            md_path.write_text(build_benchmark_markdown(report), encoding="utf-8")

            final_status = (
                RunStatus.PASSED if metrics.errored == 0 else RunStatus.FAILED
            )

            artifact_paths = [
                str(p.relative_to(artifact_dir))
                for p in artifact_dir.rglob("*")
                if p.is_file()
            ]

            self._index.update_run(
                run_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc),
                report_path=str(report_path),
                trace_path=str(trace_path),
                artifact_paths=artifact_paths,
            )

        except Exception as exc:
            logger.exception("Benchmark run %s failed", run_id)
            self._index.update_run(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
        finally:
            self._active_tasks.pop(run_id, None)

    async def _execute_pytest_run(
        self, run_id: str, request: RunCreateRequest
    ) -> None:
        """Execute benchmark_run.py as a subprocess with run-scoped output."""

        metadata = self._index.get_run(run_id)
        if metadata is None:
            return
        artifact_dir = Path(metadata.artifact_dir)

        cmd = [
            "uv",
            "run",
            "python",
            "scripts/benchmark_run.py",
            "--suite",
            request.suite,
            "--artifacts-dir",
            str(artifact_dir),
            "--run-id",
            run_id,
        ]
        if request.include_adk:
            cmd.append("--include-adk")
        if request.no_forensic:
            cmd.append("--no-forensic")
        if request.chaos_profile:
            cmd.extend(["--chaos-profile", request.chaos_profile])
        if metadata.scenario_ids:
            for scenario_id in metadata.scenario_ids:
                cmd.extend(["--scenario-id", scenario_id])

        try:
            run_env = os.environ.copy()
            run_env["MODEL_NAME"] = metadata.model_name or MODEL_NAME
            proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=str(_REPO_ROOT),
                env=run_env,
            )

            final_status = (
                RunStatus.PASSED if proc.returncode == 0 else RunStatus.FAILED
            )

            artifact_paths = [
                str(p.relative_to(artifact_dir))
                for p in artifact_dir.rglob("*")
                if p.is_file()
            ]

            report_path = artifact_dir / "benchmark-report.json"
            trace_path = artifact_dir / "benchmark-trace.jsonl"

            self._index.update_run(
                run_id,
                status=final_status,
                completed_at=datetime.now(timezone.utc),
                report_path=str(report_path) if report_path.exists() else None,
                trace_path=str(trace_path),
                artifact_paths=artifact_paths,
            )
        except Exception as exc:
            logger.exception("Benchmark run %s failed", run_id)
            self._index.update_run(
                run_id,
                status=RunStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=str(exc),
            )
        finally:
            self._active_tasks.pop(run_id, None)

    def get_run(self, run_id: str) -> RunMetadata | None:
        """Retrieve run metadata."""
        return self._index.get_run(run_id)

    def list_runs(self) -> list[RunMetadata]:
        """List all runs."""
        return self._index.list_runs()

    def latest_successful(self) -> RunMetadata | None:
        """Get the latest successful run."""
        return self._index.latest_successful_run()
