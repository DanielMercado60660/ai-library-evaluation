"""Run index persistence with file-locking for concurrent safety.

Note: Uses fcntl for file locking, which is Unix-only (macOS/Linux).
This is acceptable as the project targets macOS/Linux environments.
"""

import fcntl
import json
import tempfile
from pathlib import Path
from typing import Any, Optional

from agents.benchmark_api_models import RunIndex, RunMetadata, RunStatus


class RunIndexManager:
    """Manages the run index file at artifacts/runs/index.json.

    Uses fcntl.flock for atomic read/write to handle concurrent
    benchmark launches safely.
    """

    def __init__(self, artifacts_dir: Path) -> None:
        self._runs_dir = artifacts_dir / "runs"
        self._index_path = self._runs_dir / "index.json"
        self._lock_path = self._runs_dir / "index.json.lock"

    def _ensure_dirs(self) -> None:
        """Create runs directory if it does not exist."""
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def load(self) -> RunIndex:
        """Load the run index, returning empty index if file missing."""
        if not self._index_path.exists():
            return RunIndex()
        try:
            with open(self._index_path) as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
            return RunIndex.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return RunIndex()

    def save(self, index: RunIndex) -> None:
        """Atomically write the run index with file locking."""
        self._ensure_dirs()
        data = index.model_dump(mode="json")
        with open(self._lock_path, "w") as lock_f:
            fcntl.flock(lock_f, fcntl.LOCK_EX)
            try:
                fd, tmp_path = tempfile.mkstemp(
                    dir=str(self._runs_dir), suffix=".tmp"
                )
                try:
                    with open(fd, "w") as tmp_f:
                        json.dump(data, tmp_f, indent=2, default=str)
                    Path(tmp_path).replace(self._index_path)
                except BaseException:
                    Path(tmp_path).unlink(missing_ok=True)
                    raise
            finally:
                fcntl.flock(lock_f, fcntl.LOCK_UN)

    def add_run(self, metadata: RunMetadata) -> None:
        """Append a run entry to the index (atomic)."""
        index = self.load()
        index.runs.append(metadata)
        self.save(index)

    def update_run(self, run_id: str, **updates: Any) -> RunMetadata:
        """Update fields on an existing run entry (atomic).

        Raises:
            KeyError: If run_id is not found in the index.
        """
        index = self.load()
        for run in index.runs:
            if run.run_id == run_id:
                for key, value in updates.items():
                    if isinstance(value, RunStatus):
                        run.status = value
                    else:
                        setattr(run, key, value)
                self.save(index)
                return run
        raise KeyError(f"Run '{run_id}' not found in index")

    def get_run(self, run_id: str) -> Optional[RunMetadata]:
        """Retrieve a single run's metadata by ID."""
        index = self.load()
        for run in index.runs:
            if run.run_id == run_id:
                return run
        return None

    def list_runs(self) -> list[RunMetadata]:
        """List all runs, most recent first."""
        index = self.load()
        return sorted(index.runs, key=lambda r: r.started_at, reverse=True)

    def latest_successful_run(self) -> Optional[RunMetadata]:
        """Return the most recent run with status passed."""
        runs = self.list_runs()
        for run in runs:
            if run.status == RunStatus.PASSED:
                return run
        return None

    def run_artifact_dir(self, run_id: str) -> Path:
        """Return the artifact directory path for a given run_id."""
        return self._runs_dir / run_id
