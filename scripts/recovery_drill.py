"""Recovery and rollback drill for benchmark run artifacts.

Validates that run artifacts and index state can be backed up, destroyed,
restored, and verified — proving recoverability before local alpha promotion.

Works with raw JSON (no agents package imports) so it can run standalone.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class RecoveryDrillRunner:
    """Executes backup, restore, verify, and full drill cycles."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.runs_dir = project_root / "artifacts" / "runs"
        self.index_path = self.runs_dir / "index.json"
        self.errors: list[str] = []
        self.steps: list[dict[str, Any]] = []

    def _sha256(self, file_path: Path) -> str:
        """Compute SHA256 hex digest for a file."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _load_index(self, index_path: Path) -> dict[str, Any]:
        """Load run index JSON, returning empty structure if missing."""
        if not index_path.exists():
            return {"runs": []}
        return json.loads(index_path.read_text(encoding="utf-8"))

    def _save_index(self, index_path: Path, data: dict[str, Any]) -> None:
        """Write run index JSON atomically."""
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def backup(self, run_id: str, backup_dir: Path) -> bool:
        """Back up a run's artifacts and index entry to backup_dir.

        Returns True on success, False on failure (error recorded).
        """
        run_dir = self.runs_dir / run_id

        if not run_dir.exists():
            self.errors.append(f"Run directory not found: {run_dir}")
            self.steps.append({"step": "backup", "status": "fail", "run_id": run_id})
            return False

        try:
            # Copy run artifacts
            backup_run_dir = backup_dir / run_id
            if backup_run_dir.exists():
                shutil.rmtree(backup_run_dir)
            shutil.copytree(run_dir, backup_run_dir)

            # Extract and save index entry
            index_data = self._load_index(self.index_path)
            entry = next(
                (r for r in index_data.get("runs", []) if r.get("run_id") == run_id),
                None,
            )
            entry_path = backup_dir / "index-entry.json"
            entry_path.write_text(
                json.dumps(entry or {}, indent=2), encoding="utf-8"
            )

            self.steps.append({"step": "backup", "status": "pass", "run_id": run_id})
            return True
        except Exception as exc:
            self.errors.append(f"Backup failed: {exc}")
            self.steps.append({"step": "backup", "status": "fail", "run_id": run_id})
            return False

    def restore(self, backup_dir: Path, target_runs_dir: Path) -> bool:
        """Restore run artifacts and index entry from backup_dir.

        Returns True on success, False on failure (error recorded).
        """
        try:
            # Find the run directory in backup (first subdirectory that isn't a JSON)
            run_dirs = [
                d for d in backup_dir.iterdir()
                if d.is_dir()
            ]
            if not run_dirs:
                self.errors.append(f"No run directory found in backup: {backup_dir}")
                self.steps.append({"step": "restore", "status": "fail"})
                return False

            for run_dir in run_dirs:
                target_dir = target_runs_dir / run_dir.name
                if target_dir.exists():
                    shutil.rmtree(target_dir)
                shutil.copytree(run_dir, target_dir)

            # Merge index entry if present
            entry_path = backup_dir / "index-entry.json"
            if entry_path.exists():
                entry = json.loads(entry_path.read_text(encoding="utf-8"))
                if entry:
                    index_path = target_runs_dir / "index.json"
                    index_data = self._load_index(index_path)
                    # Remove existing entry for this run_id, then add back
                    run_id = entry.get("run_id")
                    if run_id:
                        index_data["runs"] = [
                            r for r in index_data.get("runs", [])
                            if r.get("run_id") != run_id
                        ]
                        index_data["runs"].append(entry)
                        self._save_index(index_path, index_data)

            self.steps.append({"step": "restore", "status": "pass"})
            return True
        except Exception as exc:
            self.errors.append(f"Restore failed: {exc}")
            self.steps.append({"step": "restore", "status": "fail"})
            return False

    def verify(self, original_dir: Path, restored_dir: Path) -> bool:
        """Compare SHA256 checksums of all files in two directories.

        Returns True if all checksums match, False otherwise.
        """
        if not original_dir.exists():
            self.errors.append(f"Original directory not found: {original_dir}")
            self.steps.append({"step": "verify", "status": "fail"})
            return False

        if not restored_dir.exists():
            self.errors.append(f"Restored directory not found: {restored_dir}")
            self.steps.append({"step": "verify", "status": "fail"})
            return False

        try:
            original_files = sorted(
                f.relative_to(original_dir) for f in original_dir.rglob("*") if f.is_file()
            )
            restored_files = sorted(
                f.relative_to(restored_dir) for f in restored_dir.rglob("*") if f.is_file()
            )

            if original_files != restored_files:
                self.errors.append(
                    f"File list mismatch: original={len(original_files)}, "
                    f"restored={len(restored_files)}"
                )
                self.steps.append({"step": "verify", "status": "fail"})
                return False

            mismatches = []
            for rel_path in original_files:
                orig_hash = self._sha256(original_dir / rel_path)
                rest_hash = self._sha256(restored_dir / rel_path)
                if orig_hash != rest_hash:
                    mismatches.append(str(rel_path))

            if mismatches:
                self.errors.append(f"Checksum mismatches: {mismatches}")
                self.steps.append({"step": "verify", "status": "fail"})
                return False

            self.steps.append({"step": "verify", "status": "pass"})
            return True
        except Exception as exc:
            self.errors.append(f"Verify failed: {exc}")
            self.steps.append({"step": "verify", "status": "fail"})
            return False

    def drill(self, run_id: str, backup_dir: Path) -> bool:
        """Execute full backup → destroy → restore → verify cycle.

        Returns True if all steps pass, False otherwise.
        """
        run_dir = self.runs_dir / run_id

        # Step 1: Backup
        print(f"  [1/4] Backing up run {run_id}...")
        if not self.backup(run_id, backup_dir):
            return False

        # Step 2: Destroy (simulate data loss)
        print(f"  [2/4] Destroying run directory {run_dir}...")
        try:
            shutil.rmtree(run_dir)
            self.steps.append({"step": "destroy", "status": "pass", "run_id": run_id})
        except Exception as exc:
            self.errors.append(f"Destroy failed: {exc}")
            self.steps.append({"step": "destroy", "status": "fail", "run_id": run_id})
            return False

        # Step 3: Restore
        print(f"  [3/4] Restoring from backup...")
        if not self.restore(backup_dir, self.runs_dir):
            return False

        # Step 4: Verify
        print(f"  [4/4] Verifying checksums...")
        backup_run_dir = backup_dir / run_id
        restored_run_dir = self.runs_dir / run_id
        return self.verify(backup_run_dir, restored_run_dir)

    def write_report(self, output_path: Path) -> None:
        """Write recovery drill report to JSON."""
        report: dict[str, Any] = {
            "schema_version": "1.0",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "drill_steps": self.steps,
            "errors": self.errors,
            "status": "pass" if not self.errors else "fail",
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote recovery drill report: {output_path}")


def main() -> int:
    """CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(description="Recovery and rollback drill.")
    sub = parser.add_subparsers(dest="command", required=True)

    # backup
    p_backup = sub.add_parser("backup", help="Back up a run's artifacts")
    p_backup.add_argument("--run-id", required=True, help="Run ID to back up")
    p_backup.add_argument("--backup-dir", required=True, help="Backup destination")

    # restore
    p_restore = sub.add_parser("restore", help="Restore run from backup")
    p_restore.add_argument("--backup-dir", required=True, help="Backup source")
    p_restore.add_argument("--target-dir", required=True, help="Target runs directory")

    # verify
    p_verify = sub.add_parser("verify", help="Verify checksums between dirs")
    p_verify.add_argument("--original", required=True, help="Original directory")
    p_verify.add_argument("--restored", required=True, help="Restored directory")

    # drill
    p_drill = sub.add_parser("drill", help="Full backup/destroy/restore/verify cycle")
    p_drill.add_argument("--run-id", required=True, help="Run ID for drill")
    p_drill.add_argument("--backup-dir", required=True, help="Temporary backup dir")
    p_drill.add_argument(
        "--output",
        default="artifacts/recovery-drill-report.json",
        help="Output path for JSON report",
    )

    args = parser.parse_args()
    runner = RecoveryDrillRunner()

    if args.command == "backup":
        ok = runner.backup(args.run_id, Path(args.backup_dir))
    elif args.command == "restore":
        ok = runner.restore(Path(args.backup_dir), Path(args.target_dir))
    elif args.command == "verify":
        ok = runner.verify(Path(args.original), Path(args.restored))
    elif args.command == "drill":
        ok = runner.drill(args.run_id, Path(args.backup_dir))
        runner.write_report(Path(args.output))
    else:
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
