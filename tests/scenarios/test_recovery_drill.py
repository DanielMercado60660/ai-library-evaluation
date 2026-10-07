"""Recovery drill tests.

Validates that the recovery runbook exists, the drill script is functional,
and backup/restore/verify operations work correctly on synthetic run artifacts.
"""

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
DOCS_DIR = PROJECT_ROOT / "docs" / "development"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


class TestRecoveryRunbook:
    """Verify recovery runbook documentation exists and is complete."""

    def test_runbook_exists(self):
        """RECOVERY_AND_ROLLBACK_RUNBOOK.md is present."""
        doc = DOCS_DIR / "RECOVERY_AND_ROLLBACK_RUNBOOK.md"
        assert doc.exists(), f"Missing {doc}"

    def test_runbook_documents_procedures(self):
        """Runbook contains Backup, Restore, and Verify sections."""
        doc = DOCS_DIR / "RECOVERY_AND_ROLLBACK_RUNBOOK.md"
        content = doc.read_text(encoding="utf-8")
        for section in ["Backup", "Restore", "Verify"]:
            assert section in content, f"Runbook missing section: {section}"


class TestRecoveryDrillScript:
    """Verify recovery_drill.py is importable and well-formed."""

    def test_recovery_drill_script_exists(self):
        """scripts/recovery_drill.py is present."""
        assert (SCRIPTS_DIR / "recovery_drill.py").exists()

    def test_recovery_drill_imports_cleanly(self):
        """Module imports and exposes RecoveryDrillRunner."""
        from recovery_drill import RecoveryDrillRunner

        assert RecoveryDrillRunner is not None

    def test_recovery_drill_runner_has_required_methods(self):
        """RecoveryDrillRunner has backup, restore, verify, and drill."""
        from recovery_drill import RecoveryDrillRunner

        runner = RecoveryDrillRunner(project_root=PROJECT_ROOT)
        for method_name in ["backup", "restore", "verify", "drill"]:
            assert callable(getattr(runner, method_name, None)), (
                f"Missing method: {method_name}"
            )


def _create_synthetic_run(runs_dir: Path, run_id: str) -> Path:
    """Create a synthetic run directory with artifacts and index entry."""
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Create synthetic artifacts
    report = {"schema_version": "1.3", "run_id": run_id, "results": []}
    (run_dir / "benchmark-report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (run_dir / "trace.jsonl").write_text(
        '{"event": "test", "run_id": "' + run_id + '"}\n', encoding="utf-8"
    )

    # Create index with this run's entry
    index_path = runs_dir / "index.json"
    index_data = {"runs": [{"run_id": run_id, "status": "completed"}]}
    index_path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    return run_dir


class TestBackupOperation:
    """Test backup functionality with synthetic runs."""

    def test_backup_creates_expected_structure(self, tmp_path: Path):
        """Backup creates run dir and index-entry.json in backup location."""
        from recovery_drill import RecoveryDrillRunner

        runs_dir = tmp_path / "artifacts" / "runs"
        run_id = "test-run-001"
        _create_synthetic_run(runs_dir, run_id)

        runner = RecoveryDrillRunner(project_root=tmp_path)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        assert runner.backup(run_id, backup_dir) is True

        # Verify backup structure
        assert (backup_dir / run_id).is_dir()
        assert (backup_dir / run_id / "benchmark-report.json").exists()
        assert (backup_dir / run_id / "trace.jsonl").exists()
        assert (backup_dir / "index-entry.json").exists()

        # Verify index entry content
        entry = json.loads(
            (backup_dir / "index-entry.json").read_text(encoding="utf-8")
        )
        assert entry["run_id"] == run_id

    def test_backup_fails_for_missing_run(self, tmp_path: Path):
        """Backup gracefully fails with error recorded for missing run."""
        from recovery_drill import RecoveryDrillRunner

        runs_dir = tmp_path / "artifacts" / "runs"
        runs_dir.mkdir(parents=True)

        runner = RecoveryDrillRunner(project_root=tmp_path)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        assert runner.backup("nonexistent-run", backup_dir) is False
        assert len(runner.errors) == 1
        assert "not found" in runner.errors[0]


class TestRestoreOperation:
    """Test restore functionality."""

    def test_restore_recreates_artifacts(self, tmp_path: Path):
        """Restore from backup creates run dir and updates index."""
        from recovery_drill import RecoveryDrillRunner

        runs_dir = tmp_path / "artifacts" / "runs"
        run_id = "test-run-002"
        _create_synthetic_run(runs_dir, run_id)

        runner = RecoveryDrillRunner(project_root=tmp_path)
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()

        # Backup, then destroy original
        runner.backup(run_id, backup_dir)
        import shutil
        shutil.rmtree(runs_dir / run_id)

        # Restore
        target_dir = tmp_path / "restored" / "runs"
        target_dir.mkdir(parents=True)
        assert runner.restore(backup_dir, target_dir) is True

        # Verify restored artifacts
        assert (target_dir / run_id / "benchmark-report.json").exists()
        assert (target_dir / run_id / "trace.jsonl").exists()


class TestVerifyOperation:
    """Test checksum verification."""

    def test_verify_passes_for_identical_dirs(self, tmp_path: Path):
        """Matching checksums produce a pass result."""
        from recovery_drill import RecoveryDrillRunner

        original = tmp_path / "original"
        restored = tmp_path / "restored"
        original.mkdir()
        restored.mkdir()

        content = b'{"test": "data", "value": 42}'
        (original / "file.json").write_bytes(content)
        (restored / "file.json").write_bytes(content)

        runner = RecoveryDrillRunner(project_root=tmp_path)
        assert runner.verify(original, restored) is True
        assert len(runner.errors) == 0

    def test_verify_fails_for_mismatched_checksums(self, tmp_path: Path):
        """Different content produces a fail result with errors."""
        from recovery_drill import RecoveryDrillRunner

        original = tmp_path / "original"
        restored = tmp_path / "restored"
        original.mkdir()
        restored.mkdir()

        (original / "file.json").write_bytes(b'{"original": true}')
        (restored / "file.json").write_bytes(b'{"original": false}')

        runner = RecoveryDrillRunner(project_root=tmp_path)
        assert runner.verify(original, restored) is False
        assert len(runner.errors) == 1
        assert "mismatch" in runner.errors[0].lower()
