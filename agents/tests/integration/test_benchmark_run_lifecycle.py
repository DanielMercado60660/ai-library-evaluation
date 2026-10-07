"""Benchmark run lifecycle integration tests for v1.5."""

import asyncio
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from agents.benchmark_api_models import RunCreateRequest, RunMetadata, RunStatus
from agents.benchmark_orchestrator import BenchmarkOrchestrator
from agents.run_index import RunIndexManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_synthetic_report(artifact_dir: Path) -> None:
    """Write a minimal benchmark report and trace to the artifact directory."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "1.5",
        "suite": "smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pytest_exit_code": 0,
        "summary": {"total": 5, "passed": 5, "failed": 0},
    }
    (artifact_dir / "benchmark-report.json").write_text(json.dumps(report))
    trace_event = {
        "trace_id": "trace-test",
        "run_id": "run-test",
        "event_type": "benchmark_run_start",
        "source": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {},
    }
    (artifact_dir / "benchmark-trace.jsonl").write_text(json.dumps(trace_event) + "\n")


def _write_comparison_report(
    artifact_dir: Path,
    *,
    completion_rate_percent: float,
    policy_compliance_percent: float,
    tool_precision_percent: float,
    hallucinations: int,
) -> None:
    """Write deterministic report fixture with comparison-ready metrics."""
    artifact_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "1.5",
        "suite": "scenarios",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pytest_exit_code": 0,
        "summary": {
            "total": 2,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
            "completion": round(completion_rate_percent / 100.0, 4),
            "step_accuracy": 1.0,
            "policy_compliance": round(policy_compliance_percent / 100.0, 4),
            "hallucinations": hallucinations,
            "tool_calls_total": 4,
            "tool_calls_correct": int(round((tool_precision_percent / 100.0) * 4)),
            "tool_precision": round(tool_precision_percent / 100.0, 4),
            "completion_rate_percent": completion_rate_percent,
            "step_accuracy_percent": 100.0,
            "policy_compliance_percent": policy_compliance_percent,
            "tool_precision_percent": tool_precision_percent,
        },
        "taxonomy_counts": {},
        "scenarios": [
            {
                "scenario_id": "tier1_author_search",
                "nodeid": "tests::tier1_author_search",
                "status": "passed",
                "tier": 1,
                "duration_seconds": 1.25,
                "completion": round((completion_rate_percent / 100.0), 4),
                "step_accuracy": 1.0,
                "policy_compliance": round((policy_compliance_percent / 100.0), 4),
                "hallucinations": hallucinations,
                "tool_calls_total": 2,
                "tool_calls_correct": int(round((tool_precision_percent / 100.0) * 2)),
                "taxonomy": "none",
                "detail": "",
            },
            {
                "scenario_id": "tier2_checkout_flow",
                "nodeid": "tests::tier2_checkout_flow",
                "status": "passed",
                "tier": 2,
                "duration_seconds": 1.75,
                "completion": round((completion_rate_percent / 100.0), 4),
                "step_accuracy": 1.0,
                "policy_compliance": round((policy_compliance_percent / 100.0), 4),
                "hallucinations": hallucinations,
                "tool_calls_total": 2,
                "tool_calls_correct": int(round((tool_precision_percent / 100.0) * 2)),
                "taxonomy": "none",
                "detail": "",
            },
        ],
        "forensic_assertions": [],
    }
    (artifact_dir / "benchmark-report.json").write_text(json.dumps(report))
    trace_event = {
        "trace_id": "trace-compare",
        "run_id": "run-compare",
        "event_type": "benchmark_run_start",
        "source": "test",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": {},
    }
    (artifact_dir / "benchmark-trace.jsonl").write_text(json.dumps(trace_event) + "\n")


def _build_app(tmp_path: Path):
    """Build a fresh FastAPI app with an orchestrator rooted at tmp_path."""
    import agents.api as api_module

    original_artifacts = api_module.ARTIFACTS_DIR
    original_orchestrator = api_module.orchestrator

    api_module.ARTIFACTS_DIR = tmp_path
    api_module.orchestrator = BenchmarkOrchestrator(tmp_path)

    yield api_module.app, api_module.orchestrator

    api_module.ARTIFACTS_DIR = original_artifacts
    api_module.orchestrator = original_orchestrator


@pytest.fixture
def app_and_orchestrator(tmp_path):
    """Provide a fresh app + orchestrator backed by tmp_path."""
    import agents.api as api_module

    original_artifacts = api_module.ARTIFACTS_DIR
    original_orchestrator = api_module.orchestrator

    api_module.ARTIFACTS_DIR = tmp_path
    api_module.orchestrator = BenchmarkOrchestrator(tmp_path)

    yield api_module.app, api_module.orchestrator

    api_module.ARTIFACTS_DIR = original_artifacts
    api_module.orchestrator = original_orchestrator


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBenchmarkRunLifecycle:
    """Validate the async orchestration API lifecycle."""

    @pytest.mark.asyncio
    async def test_create_run_returns_202_with_run_id(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """POST /benchmark/runs returns 202 with a run_id."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["run_id"].startswith("run-")
        assert data["status"] == "queued"
        assert "artifact_dir" in data
        assert data["model_name"]
        assert data["model_family"] == "gemini"
        assert data["scenario_ids"] == []
        assert data["trigger_source"] == "manual"
        assert data["actor_patron_id"] is None

    @pytest.mark.asyncio
    async def test_create_run_creates_artifact_directory(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """Created run has a real directory at artifacts/runs/<run_id>/."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )

        run_id = resp.json()["run_id"]
        assert (tmp_path / "runs" / run_id).is_dir()

    @pytest.mark.asyncio
    async def test_list_runs_empty_initially(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/runs returns empty list when no runs exist."""
        app, _ = app_and_orchestrator
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["runs"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_runs_after_create(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/runs includes created run."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/benchmark/runs", json={"suite": "smoke"})
                resp = await client.get("/benchmark/runs")

        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["suite"] == "smoke"

    @pytest.mark.asyncio
    async def test_get_run_by_id(self, app_and_orchestrator) -> None:
        """GET /benchmark/runs/{run_id} returns correct metadata."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "scenarios"}
                )
                run_id = create_resp.json()["run_id"]
                resp = await client.get(f"/benchmark/runs/{run_id}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["suite"] == "scenarios"

    @pytest.mark.asyncio
    async def test_get_run_404_for_unknown(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/runs/nonexistent returns 404."""
        app, _ = app_and_orchestrator
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/runs/run-nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_report_404_before_completion(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/runs/{run_id}/report returns 404 for queued run."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]
                resp = await client.get(f"/benchmark/runs/{run_id}/report")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_run_trace_returns_empty_list_while_active(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/runs/{run_id}/trace returns [] for queued/running runs."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]
                resp = await client.get(f"/benchmark/runs/{run_id}/trace")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_run_report_available_after_completion(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/runs/{run_id}/report serves JSON after run completes."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]

        # Simulate completion: write report and update index
        run_dir = tmp_path / "runs" / run_id
        _write_synthetic_report(run_dir)
        orch._index.update_run(
            run_id,
            status=RunStatus.PASSED,
            completed_at=datetime.now(timezone.utc),
            report_path=str(run_dir / "benchmark-report.json"),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/benchmark/runs/{run_id}/report")

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "1.5"
        assert data["summary"]["passed"] == 5

    @pytest.mark.asyncio
    async def test_run_trace_available_after_completion(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/runs/{run_id}/trace serves trace events."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]

        run_dir = tmp_path / "runs" / run_id
        _write_synthetic_report(run_dir)
        orch._index.update_run(
            run_id,
            status=RunStatus.PASSED,
            completed_at=datetime.now(timezone.utc),
            trace_path=str(run_dir / "benchmark-trace.jsonl"),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/benchmark/runs/{run_id}/trace")

        assert resp.status_code == 200
        events = resp.json()
        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["event_type"] == "benchmark_run_start"

    @pytest.mark.asyncio
    async def test_run_artifacts_list(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/runs/{run_id}/artifacts lists generated files."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]

        run_dir = tmp_path / "runs" / run_id
        _write_synthetic_report(run_dir)
        orch._index.update_run(
            run_id,
            status=RunStatus.PASSED,
            artifact_paths=["benchmark-report.json", "benchmark-trace.jsonl"],
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/benchmark/runs/{run_id}/artifacts")

        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "benchmark-report.json" in data["artifacts"]

    @pytest.mark.asyncio
    async def test_legacy_report_endpoint_compatibility(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/report resolves to latest successful run."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs", json={"suite": "smoke"}
                )
                run_id = create_resp.json()["run_id"]

        run_dir = tmp_path / "runs" / run_id
        _write_synthetic_report(run_dir)
        orch._index.update_run(
            run_id,
            status=RunStatus.PASSED,
            completed_at=datetime.now(timezone.utc),
            report_path=str(run_dir / "benchmark-report.json"),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/report")

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "1.5"

    @pytest.mark.asyncio
    async def test_legacy_report_falls_back_to_flat_artifact(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/report falls back to flat artifacts/ when no runs."""
        app, _ = app_and_orchestrator

        # Write a legacy flat report
        legacy_report = {"schema_version": "1.3", "suite": "scenarios"}
        (tmp_path / "benchmark-report.json").write_text(json.dumps(legacy_report))

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/report")

        assert resp.status_code == 200
        data = resp.json()
        assert data["schema_version"] == "1.3"

    @pytest.mark.asyncio
    async def test_legacy_report_404_when_nothing_exists(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/report returns 404 when no runs and no flat file."""
        app, _ = app_and_orchestrator
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/report")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_benchmark_scenarios_endpoint_serves_manifest_and_scripts(
        self, app_and_orchestrator, tmp_path, monkeypatch
    ) -> None:
        """GET /benchmark/scenarios returns manifest metadata plus chat scripts."""
        app, _ = app_and_orchestrator
        import agents.api as api_module

        manifest_payload = {
            "manifest_version": "test-1.0",
            "suite": "smoke",
            "generated_at": "2026-02-10T00:00:00Z",
            "scenarios": [
                {
                    "id": "tier1_author_search",
                    "nodeid_pattern": "test_tier1_find_book_by_author",
                    "tier": 1,
                    "expected_steps": 3,
                    "policy_checks": 1,
                    "tool_calls_total": 1,
                    "taxonomy_hint": "tool_misuse",
                }
            ],
        }
        scripts_payload = {
            "scripts": {
                "tier1_author_search": [
                    "Do you have any books by Maren Greyhorn?",
                ]
            }
        }

        manifest_path = tmp_path / "scenario_manifest.json"
        scripts_path = tmp_path / "scenario_chat_scripts.json"
        manifest_path.write_text(json.dumps(manifest_payload))
        scripts_path.write_text(json.dumps(scripts_payload))

        monkeypatch.setattr(api_module, "SCENARIO_MANIFEST_PATH", manifest_path)
        monkeypatch.setattr(api_module, "SCENARIO_SCRIPTS_PATH", scripts_path)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/scenarios")

        assert resp.status_code == 200
        data = resp.json()
        assert data["manifest_version"] == "test-1.0"
        assert data["suite"] == "smoke"
        assert len(data["scenarios"]) == 1
        assert data["scenarios"][0]["id"] == "tier1_author_search"
        assert len(data["scenarios"][0]["steps"]) >= 1
        assert data["scenarios"][0]["steps"][0]["step_id"] == "intake_request"
        assert data["scripts"]["tier1_author_search"][0].startswith("Do you have")

    @pytest.mark.asyncio
    async def test_benchmark_scenarios_endpoint_404_when_manifest_missing(
        self, app_and_orchestrator, tmp_path, monkeypatch
    ) -> None:
        """GET /benchmark/scenarios returns 404 when manifest file is missing."""
        app, _ = app_and_orchestrator
        import agents.api as api_module

        missing_manifest_path = tmp_path / "missing_manifest.json"
        scripts_path = tmp_path / "scenario_chat_scripts.json"
        scripts_path.write_text(json.dumps({"scripts": {}}))

        monkeypatch.setattr(api_module, "SCENARIO_MANIFEST_PATH", missing_manifest_path)
        monkeypatch.setattr(api_module, "SCENARIO_SCRIPTS_PATH", scripts_path)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/scenarios")

        assert resp.status_code == 404
        assert resp.json()["detail"] == "Scenario manifest not found"

    @pytest.mark.asyncio
    async def test_create_run_stores_selected_model_name(
        self, app_and_orchestrator
    ) -> None:
        """POST /benchmark/runs persists caller-provided model_name."""
        app, orch = app_and_orchestrator
        requested_model = "gemini-3.0-pro"

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": requested_model},
                )

        run_id = create_resp.json()["run_id"]
        stored = orch.get_run(run_id)
        assert stored is not None
        assert stored.model_name == requested_model
        assert stored.model_family == "gemini"

    @pytest.mark.asyncio
    async def test_create_run_stores_selected_scenario_ids_and_trigger_source(
        self, app_and_orchestrator
    ) -> None:
        """POST /benchmark/runs persists scenario_ids and trigger_source."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs",
                    json={
                        "suite": "scenarios",
                        "scenario_ids": ["tier1_author_search", "tier1_author_search"],
                        "trigger_source": "assistant_card",
                    },
                )

        assert create_resp.status_code == 202
        payload = create_resp.json()
        run_id = payload["run_id"]
        stored = orch.get_run(run_id)
        assert stored is not None
        assert stored.scenario_ids == ["tier1_author_search"]
        assert stored.trigger_source == "assistant_card"
        assert payload["scenario_ids"] == ["tier1_author_search"]
        assert payload["trigger_source"] == "assistant_card"

    @pytest.mark.asyncio
    async def test_create_run_round_trips_actor_patron_id(
        self, app_and_orchestrator
    ) -> None:
        """POST /benchmark/runs persists actor_patron_id metadata additively."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs",
                    json={
                        "suite": "scenarios",
                        "scenario_ids": ["tier1_author_search"],
                        "trigger_source": "assistant_card",
                        "actor_patron_id": "patron-003",
                    },
                )

        assert create_resp.status_code == 202
        payload = create_resp.json()
        run_id = payload["run_id"]
        stored = orch.get_run(run_id)
        assert stored is not None
        assert stored.actor_patron_id == "patron-003"
        assert payload["actor_patron_id"] == "patron-003"

    @pytest.mark.asyncio
    async def test_create_run_rejects_unknown_scenario_ids(
        self, app_and_orchestrator
    ) -> None:
        """POST /benchmark/runs rejects scenario_ids not present in manifest."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs",
                    json={
                        "suite": "scenarios",
                        "scenario_ids": ["scenario_does_not_exist"],
                    },
                )

        assert create_resp.status_code == 400
        assert "Unknown scenario id" in create_resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_run_rejects_scenario_ids_for_non_scenario_suite(
        self, app_and_orchestrator
    ) -> None:
        """POST /benchmark/runs rejects scenario_ids when suite is not scenarios."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                create_resp = await client.post(
                    "/benchmark/runs",
                    json={
                        "suite": "smoke",
                        "scenario_ids": ["tier1_author_search"],
                    },
                )

        assert create_resp.status_code == 400
        assert "suite='scenarios'" in create_resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_orchestrator_passes_scenario_ids_as_cli_args(
        self, tmp_path
    ) -> None:
        """Orchestrator forwards scenario ids to benchmark runner CLI."""
        orchestrator = BenchmarkOrchestrator(tmp_path)
        request = RunCreateRequest(
            suite="scenarios",
            scenario_ids=["tier1_author_search", "tier2_patron_summary"],
            trigger_source="assistant_card",
        )
        metadata = orchestrator.create_run(request)

        captured_cmd: list[str] = []

        def _fake_run(*args, **kwargs):
            nonlocal captured_cmd
            captured_cmd = list(args[0])
            artifact_dir = tmp_path / "runs" / metadata.run_id
            _write_synthetic_report(artifact_dir)
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout="ok",
                stderr="",
            )

        with patch("agents.benchmark_orchestrator.subprocess.run", side_effect=_fake_run):
            await orchestrator._execute_run(metadata.run_id, request)

        assert captured_cmd
        scenario_flags = [
            captured_cmd[idx + 1]
            for idx, token in enumerate(captured_cmd)
            if token == "--scenario-id" and idx + 1 < len(captured_cmd)
        ]
        assert scenario_flags == ["tier1_author_search", "tier2_patron_summary"]

    @pytest.mark.asyncio
    async def test_benchmark_models_endpoint_returns_catalog(
        self, app_and_orchestrator
    ) -> None:
        """GET /benchmark/models returns default + selectable variants."""
        app, _ = app_and_orchestrator
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/models")

        assert resp.status_code == 200
        data = resp.json()
        assert data["default_model"]
        assert len(data["models"]) >= 1
        assert any(model["is_default"] for model in data["models"])

    @pytest.mark.asyncio
    async def test_compare_endpoint_returns_run_and_tier_deltas(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """POST /benchmark/compare returns deterministic deltas for completed runs."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                run_a_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": "gemini-3.0-flash"},
                )
                run_b_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": "gemini-3.0-pro"},
                )

        run_a = run_a_resp.json()["run_id"]
        run_b = run_b_resp.json()["run_id"]

        run_a_dir = tmp_path / "runs" / run_a
        run_b_dir = tmp_path / "runs" / run_b
        _write_comparison_report(
            run_a_dir,
            completion_rate_percent=98.0,
            policy_compliance_percent=100.0,
            tool_precision_percent=100.0,
            hallucinations=0,
        )
        _write_comparison_report(
            run_b_dir,
            completion_rate_percent=80.0,
            policy_compliance_percent=85.0,
            tool_precision_percent=75.0,
            hallucinations=2,
        )

        orch._index.update_run(
            run_a,
            status=RunStatus.PASSED,
            completed_at=datetime.now(timezone.utc),
            report_path=str(run_a_dir / "benchmark-report.json"),
            trace_path=str(run_a_dir / "benchmark-trace.jsonl"),
        )
        orch._index.update_run(
            run_b,
            status=RunStatus.PASSED,
            completed_at=datetime.now(timezone.utc),
            report_path=str(run_b_dir / "benchmark-report.json"),
            trace_path=str(run_b_dir / "benchmark-trace.jsonl"),
        )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/benchmark/compare",
                json={"run_ids": [run_a, run_b], "suite": "scenarios"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["baseline_run_id"] == run_a
        assert len(data["runs"]) == 2
        assert len(data["run_deltas"]) == 1
        assert len(data["tier_deltas"]) >= 1
        assert len(data["scenario_deltas"]) >= 1
        assert data["ranked_run_ids"][0] == run_a

    @pytest.mark.asyncio
    async def test_leaderboard_endpoint_returns_sorted_rows(
        self, app_and_orchestrator, tmp_path
    ) -> None:
        """GET /benchmark/leaderboard sorts rows by composite score contract."""
        app, orch = app_and_orchestrator

        with patch.object(orch, "launch_run", new_callable=AsyncMock):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                run_a_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": "gemini-3.0-flash"},
                )
                run_b_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": "gemini-3.0-flash"},
                )
                run_c_resp = await client.post(
                    "/benchmark/runs",
                    json={"suite": "scenarios", "model_name": "gemini-3.0-pro"},
                )

        run_a = run_a_resp.json()["run_id"]
        run_b = run_b_resp.json()["run_id"]
        run_c = run_c_resp.json()["run_id"]

        run_a_dir = tmp_path / "runs" / run_a
        run_b_dir = tmp_path / "runs" / run_b
        run_c_dir = tmp_path / "runs" / run_c
        _write_comparison_report(
            run_a_dir,
            completion_rate_percent=99.0,
            policy_compliance_percent=100.0,
            tool_precision_percent=100.0,
            hallucinations=0,
        )
        _write_comparison_report(
            run_b_dir,
            completion_rate_percent=95.0,
            policy_compliance_percent=98.0,
            tool_precision_percent=96.0,
            hallucinations=0,
        )
        _write_comparison_report(
            run_c_dir,
            completion_rate_percent=70.0,
            policy_compliance_percent=80.0,
            tool_precision_percent=75.0,
            hallucinations=2,
        )

        for run_id, run_dir in ((run_a, run_a_dir), (run_b, run_b_dir), (run_c, run_c_dir)):
            orch._index.update_run(
                run_id,
                status=RunStatus.PASSED,
                completed_at=datetime.now(timezone.utc),
                report_path=str(run_dir / "benchmark-report.json"),
                trace_path=str(run_dir / "benchmark-trace.jsonl"),
            )

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/benchmark/leaderboard?suite=scenarios&min_runs=1")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_models"] == 2
        assert data["rows"][0]["model_name"] == "gemini-3.0-flash"
        assert data["rows"][0]["rank"] == 1
