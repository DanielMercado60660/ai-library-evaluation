"""Run index integrity tests for v1.5 artifact partitioning."""

from datetime import datetime, timezone, timedelta
import json
from pathlib import Path

import pytest

from agents.benchmark_api_models import RunIndex, RunMetadata, RunStatus
from agents.run_index import RunIndexManager


def _make_metadata(
    run_id: str = "run-test0001",
    suite: str = "smoke",
    status: RunStatus = RunStatus.QUEUED,
    started_at: datetime | None = None,
    artifact_dir: str = "artifacts/runs/run-test0001",
) -> RunMetadata:
    return RunMetadata(
        run_id=run_id,
        suite=suite,
        status=status,
        started_at=started_at or datetime.now(timezone.utc),
        artifact_dir=artifact_dir,
    )


class TestRunIndexIntegrity:
    """Validate run index persistence contract."""

    def test_empty_index_on_fresh_directory(self, tmp_path: Path) -> None:
        """Empty directory returns valid empty RunIndex."""
        mgr = RunIndexManager(tmp_path)
        index = mgr.load()
        assert isinstance(index, RunIndex)
        assert index.runs == []
        assert index.schema_version == "1.5"

    def test_add_run_creates_index_file(self, tmp_path: Path) -> None:
        """Adding a run creates index.json."""
        mgr = RunIndexManager(tmp_path)
        meta = _make_metadata(artifact_dir=str(tmp_path / "runs" / "run-test0001"))
        mgr.add_run(meta)

        index_path = tmp_path / "runs" / "index.json"
        assert index_path.exists()

        loaded = mgr.load()
        assert len(loaded.runs) == 1
        assert loaded.runs[0].run_id == "run-test0001"

    def test_add_run_assigns_unique_ids(self, tmp_path: Path) -> None:
        """Sequential adds produce distinct run_id entries."""
        mgr = RunIndexManager(tmp_path)
        mgr.add_run(_make_metadata(run_id="run-aaa", artifact_dir=str(tmp_path / "runs" / "run-aaa")))
        mgr.add_run(_make_metadata(run_id="run-bbb", artifact_dir=str(tmp_path / "runs" / "run-bbb")))

        loaded = mgr.load()
        ids = [r.run_id for r in loaded.runs]
        assert ids == ["run-aaa", "run-bbb"]
        assert len(set(ids)) == 2

    def test_update_run_status_transition(self, tmp_path: Path) -> None:
        """Updating status from queued to running to passed works."""
        mgr = RunIndexManager(tmp_path)
        mgr.add_run(_make_metadata(run_id="run-trans", artifact_dir=str(tmp_path / "runs" / "run-trans")))

        updated = mgr.update_run("run-trans", status=RunStatus.RUNNING)
        assert updated.status == RunStatus.RUNNING

        updated = mgr.update_run("run-trans", status=RunStatus.PASSED)
        assert updated.status == RunStatus.PASSED

        # Verify persisted
        loaded = mgr.get_run("run-trans")
        assert loaded is not None
        assert loaded.status == RunStatus.PASSED

    def test_get_run_returns_none_for_missing(self, tmp_path: Path) -> None:
        """Unknown run_id returns None, not an error."""
        mgr = RunIndexManager(tmp_path)
        assert mgr.get_run("run-nonexistent") is None

    def test_latest_successful_run(self, tmp_path: Path) -> None:
        """Latest successful returns most recent passed run."""
        mgr = RunIndexManager(tmp_path)
        now = datetime.now(timezone.utc)

        mgr.add_run(_make_metadata(
            run_id="run-old",
            status=RunStatus.PASSED,
            started_at=now - timedelta(hours=2),
            artifact_dir=str(tmp_path / "runs" / "run-old"),
        ))
        mgr.add_run(_make_metadata(
            run_id="run-new",
            status=RunStatus.PASSED,
            started_at=now - timedelta(hours=1),
            artifact_dir=str(tmp_path / "runs" / "run-new"),
        ))

        latest = mgr.latest_successful_run()
        assert latest is not None
        assert latest.run_id == "run-new"

    def test_latest_successful_skips_failed(self, tmp_path: Path) -> None:
        """Failed runs are not returned by latest_successful_run."""
        mgr = RunIndexManager(tmp_path)
        now = datetime.now(timezone.utc)

        mgr.add_run(_make_metadata(
            run_id="run-passed",
            status=RunStatus.PASSED,
            started_at=now - timedelta(hours=2),
            artifact_dir=str(tmp_path / "runs" / "run-passed"),
        ))
        mgr.add_run(_make_metadata(
            run_id="run-failed",
            status=RunStatus.FAILED,
            started_at=now - timedelta(hours=1),
            artifact_dir=str(tmp_path / "runs" / "run-failed"),
        ))

        latest = mgr.latest_successful_run()
        assert latest is not None
        assert latest.run_id == "run-passed"

    def test_list_runs_ordered_by_start_time(self, tmp_path: Path) -> None:
        """Runs are listed most-recent-first."""
        mgr = RunIndexManager(tmp_path)
        now = datetime.now(timezone.utc)

        mgr.add_run(_make_metadata(
            run_id="run-first",
            started_at=now - timedelta(hours=3),
            artifact_dir=str(tmp_path / "runs" / "run-first"),
        ))
        mgr.add_run(_make_metadata(
            run_id="run-second",
            started_at=now - timedelta(hours=1),
            artifact_dir=str(tmp_path / "runs" / "run-second"),
        ))
        mgr.add_run(_make_metadata(
            run_id="run-third",
            started_at=now,
            artifact_dir=str(tmp_path / "runs" / "run-third"),
        ))

        runs = mgr.list_runs()
        ids = [r.run_id for r in runs]
        assert ids == ["run-third", "run-second", "run-first"]

    def test_run_artifact_dir_path(self, tmp_path: Path) -> None:
        """Artifact dir resolves to artifacts/runs/<run_id>/."""
        mgr = RunIndexManager(tmp_path)
        result = mgr.run_artifact_dir("run-abc123")
        assert result == tmp_path / "runs" / "run-abc123"

    def test_update_run_raises_for_missing(self, tmp_path: Path) -> None:
        """Updating a nonexistent run raises KeyError."""
        mgr = RunIndexManager(tmp_path)
        with pytest.raises(KeyError, match="run-ghost"):
            mgr.update_run("run-ghost", status=RunStatus.FAILED)

    def test_load_legacy_run_index_missing_model_fields(self, tmp_path: Path) -> None:
        """Legacy v1.5 entries without model metadata load with defaults."""
        runs_dir = tmp_path / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        legacy_payload = {
            "schema_version": "1.5",
            "runs": [
                {
                    "run_id": "run-legacy",
                    "suite": "smoke",
                    "status": "passed",
                    "started_at": "2026-02-09T00:00:00Z",
                    "completed_at": "2026-02-09T00:00:01Z",
                    "artifact_dir": "artifacts/runs/run-legacy",
                    "report_path": None,
                    "trace_path": None,
                    "artifact_paths": [],
                    "error_message": None,
                }
            ],
        }
        (runs_dir / "index.json").write_text(json.dumps(legacy_payload), encoding="utf-8")

        mgr = RunIndexManager(tmp_path)
        loaded = mgr.load()
        assert len(loaded.runs) == 1
        assert loaded.runs[0].model_name == "unknown"
        assert loaded.runs[0].model_family == "gemini"
        assert loaded.runs[0].scenario_ids == []
        assert loaded.runs[0].trigger_source == "manual"
        assert loaded.runs[0].actor_patron_id is None

    def test_new_fields_round_trip_for_scenario_run(self, tmp_path: Path) -> None:
        """scenario_ids/trigger_source/actor_patron_id persist through save/load."""
        mgr = RunIndexManager(tmp_path)
        metadata = RunMetadata(
            run_id="run-assistant-001",
            suite="scenarios",
            status=RunStatus.QUEUED,
            started_at=datetime.now(timezone.utc),
            artifact_dir=str(tmp_path / "runs" / "run-assistant-001"),
            scenario_ids=["tier1_author_search"],
            trigger_source="assistant_card",
            actor_patron_id="patron-003",
        )
        mgr.add_run(metadata)

        loaded = mgr.get_run("run-assistant-001")
        assert loaded is not None
        assert loaded.scenario_ids == ["tier1_author_search"]
        assert loaded.trigger_source == "assistant_card"
        assert loaded.actor_patron_id == "patron-003"
