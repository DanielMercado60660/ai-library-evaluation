#!/usr/bin/env python3
"""Federated seed orchestrator for the Pachyderm Library Network.

Validates the network seed manifest and writes a seed report to
``artifacts/network-seed-report.json``.  In ``provision`` mode, creates
per-library SQLite catalog databases under ``artifacts/federated-dbs/``.

Usage::

    python scripts/seed_network.py                       # validate + report
    python scripts/seed_network.py --check-only          # validate only (exit 0/1)
    python scripts/seed_network.py --mode provision      # validate + seed spoke DBs
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, UTC
from pathlib import Path

# Allow importing the validator from the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_manifest_validator import ManifestValidator  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "data" / "network_seed_manifest.json"
ARTIFACTS_DIR = ROOT / "artifacts"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _library_summary(manifest: dict) -> list[dict]:
    """Build per-library summary entries."""
    summaries: list[dict] = []

    # Hub
    hub = manifest["hub"]
    hub_ids: list[str] = []
    data_dir = ROOT / "data"
    for src in hub["sources"]:
        data = json.loads((data_dir / src["file"]).read_text(encoding="utf-8"))
        hub_ids.extend(b["id"] for b in data.get(src["key"], []))
    hub_ids.sort()
    summaries.append({
        "code": hub["code"],
        "name": hub["name"],
        "role": "hub",
        "book_count": len(hub_ids),
        "id_range": f"{hub_ids[0]}–{hub_ids[-1]}" if hub_ids else "",
        "sources": [s["file"] for s in hub["sources"]],
    })

    # Spokes
    for spoke in manifest["spokes"]:
        spoke_ids: list[str] = []
        for src in spoke["sources"]:
            data = json.loads((data_dir / src["file"]).read_text(encoding="utf-8"))
            spoke_ids.extend(b["id"] for b in data.get(src["key"], []))
        spoke_ids.sort()
        summaries.append({
            "code": spoke["code"],
            "name": spoke["name"],
            "role": "spoke",
            "book_count": len(spoke_ids),
            "id_range": f"{spoke_ids[0]}–{spoke_ids[-1]}" if spoke_ids else "",
            "sources": [s["file"] for s in spoke["sources"]],
            "specializations": spoke.get("specializations", []),
        })

    return summaries


def _write_report(manifest: dict, validation_passed: int, validation_failed: int) -> Path:
    """Write network-seed-report.json to the artifacts directory."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": manifest.get("schema_version", "unknown"),
        "generated_at": datetime.now(UTC).isoformat(),
        "seed_mode": manifest.get("seed_mode", "federated"),
        "total_network_books": manifest.get("total_network_books"),
        "validation": {
            "passed": validation_passed,
            "failed": validation_failed,
        },
        "libraries": _library_summary(manifest),
        "batch_coverage": manifest.get("batch_coverage", {}),
    }
    out = ARTIFACTS_DIR / "network-seed-report.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out


def _provision_spoke_dbs(manifest: dict, summaries: list[dict]) -> int:
    """Create per-library SQLite databases under artifacts/federated-dbs/."""
    from seed_spoke_catalog import seed_library  # noqa: E402

    db_dir = ARTIFACTS_DIR / "federated-dbs"
    db_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProvisioning spoke databases in {db_dir}")
    print("-" * 40)

    results = []
    all_libraries = [manifest["hub"]] + manifest.get("spokes", [])
    for lib in all_libraries:
        code = lib["code"]
        db_path = db_dir / f"{code}.db"
        # Remove existing DB for a clean seed
        if db_path.exists():
            db_path.unlink()
        db_url = f"sqlite:///{db_path}"
        result = seed_library(code, db_url)
        results.append(result)
        print(f"  {code:25s} {result['books_seeded']:>4d} books  {result['instances_generated']:>4d} instances")

    # Write provision report
    report = {
        "schema_version": manifest.get("schema_version", "unknown"),
        "generated_at": datetime.now(UTC).isoformat(),
        "mode": "provision",
        "db_dir": str(db_dir),
        "libraries": results,
    }
    report_path = ARTIFACTS_DIR / "network-seed-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\nProvision report written to: {report_path}")

    total_books = sum(r["books_seeded"] for r in results)
    total_instances = sum(r["instances_generated"] for r in results)
    print(f"Total: {total_books} books, {total_instances} instances across {len(results)} libraries")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Federated network seed orchestrator")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Validate manifest only; do not write a report.",
    )
    parser.add_argument(
        "--mode",
        choices=["single_library", "federated", "provision"],
        default="federated",
        help="Seed mode (default: federated). 'provision' seeds spoke catalog DBs.",
    )
    args = parser.parse_args()

    if args.mode == "single_library":
        print("Single-library mode — delegating to seed_db.py")
        import subprocess
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "seed_db.py")],
            check=False,
        )
        return result.returncode

    # Validate manifest (common to federated + provision)
    print("Federated Network Seed Orchestrator")
    print("=" * 40)

    validator = ManifestValidator(MANIFEST_PATH)
    passed, failed, errors = validator.run_all()
    print(f"\nValidation: {passed} passed, {failed} failed")
    for err in errors:
        print(f"  FAIL: {err}")

    if args.check_only:
        return 0 if failed == 0 else 1

    if failed > 0:
        print("\nManifest validation failed — aborting.")
        return 1

    manifest = _load_manifest()

    # Log per-library summary
    summaries = _library_summary(manifest)
    print(f"\nLibraries: {len(summaries)}")
    for lib in summaries:
        print(f"  {lib['code']:25s} {lib['book_count']:>4d} books  {lib['id_range']}")

    if args.mode == "provision":
        return _provision_spoke_dbs(manifest, summaries)

    report_path = _write_report(manifest, passed, failed)
    print(f"\nReport written to: {report_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
