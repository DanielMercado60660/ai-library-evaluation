"""Validator for the federated network seed manifest.

Ensures batch-to-library ownership integrity, count accuracy,
and no duplicate book IDs across library partitions.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MANIFEST_PATH = DATA_DIR / "network_seed_manifest.json"

KNOWN_REGISTRY_CODES = {
    "mastodon-institute",
    "mammoth-valley",
    "ivory-university",
    "tusk-conservatory",
}


class ManifestValidator:
    """Validates the network seed manifest for integrity and completeness."""

    def __init__(self, manifest_path: Path = MANIFEST_PATH) -> None:
        self.manifest_path = manifest_path
        self.manifest: dict[str, Any] = {}
        self.errors: list[str] = []
        self.passed = 0
        self.failed = 0

    def _pass(self, name: str) -> None:
        self.passed += 1
        print(f"  PASS: {name}")

    def _fail(self, name: str, reason: str) -> None:
        self.failed += 1
        self.errors.append(f"{name}: {reason}")
        print(f"  FAIL: {name} — {reason}")

    def load(self) -> bool:
        """Load the manifest file. Returns False if file is missing or invalid JSON."""
        if not self.manifest_path.exists():
            self._fail("load", f"Manifest not found: {self.manifest_path}")
            return False
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            self._pass("load")
            return True
        except json.JSONDecodeError as exc:
            self._fail("load", f"Invalid JSON: {exc}")
            return False

    def check_schema(self) -> None:
        """Verify required top-level fields and types."""
        required = {
            "schema_version": str,
            "seed_mode": str,
            "hub": dict,
            "spokes": list,
            "total_network_books": int,
            "batch_coverage": dict,
        }
        for field, expected_type in required.items():
            if field not in self.manifest:
                self._fail("schema", f"Missing required field: {field}")
                return
            if not isinstance(self.manifest[field], expected_type):
                self._fail("schema", f"{field} should be {expected_type.__name__}")
                return
        self._pass("schema")

    def check_batch_coverage(self) -> None:
        """Every batch_*.json and main catalog must appear in batch_coverage."""
        batch_coverage = self.manifest.get("batch_coverage", {})
        data_files = {
            f.name
            for f in DATA_DIR.glob("batch_*.json")
        }
        data_files.add("hanno_memorial_library_catalog.json")

        missing = data_files - set(batch_coverage.keys())
        extra = set(batch_coverage.keys()) - data_files

        if missing:
            self._fail("batch_coverage", f"Unassigned data files: {sorted(missing)}")
        elif extra:
            self._fail("batch_coverage", f"Unknown files in coverage: {sorted(extra)}")
        else:
            self._pass("batch_coverage")

    def check_no_duplicate_assignments(self) -> None:
        """Each batch file appears in exactly one library's sources."""
        all_sources: list[str] = []
        hub = self.manifest.get("hub", {})
        for src in hub.get("sources", []):
            all_sources.append(src["file"])
        for spoke in self.manifest.get("spokes", []):
            for src in spoke.get("sources", []):
                all_sources.append(src["file"])

        dupes = [f for f, count in Counter(all_sources).items() if count > 1]
        if dupes:
            self._fail("no_duplicate_assignments", f"Files assigned to multiple libraries: {dupes}")
        else:
            self._pass("no_duplicate_assignments")

    def check_counts(self) -> None:
        """Declared source counts match actual book array lengths in data files."""
        errors: list[str] = []

        def _check_sources(library_code: str, sources: list[dict]) -> None:
            for src in sources:
                path = DATA_DIR / src["file"]
                if not path.exists():
                    errors.append(f"{library_code}: file not found: {src['file']}")
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                actual = len(data.get(src["key"], []))
                if actual != src["count"]:
                    errors.append(
                        f"{library_code}/{src['file']}: declared {src['count']}, actual {actual}"
                    )

        hub = self.manifest.get("hub", {})
        _check_sources(hub.get("code", "hub"), hub.get("sources", []))
        for spoke in self.manifest.get("spokes", []):
            _check_sources(spoke.get("code", "?"), spoke.get("sources", []))

        if errors:
            self._fail("counts", "; ".join(errors))
        else:
            self._pass("counts")

    def check_no_duplicate_ids(self) -> None:
        """No book ID appears in two different library partitions."""
        id_to_library: dict[str, str] = {}
        duplicates: list[str] = []

        def _collect(library_code: str, sources: list[dict]) -> None:
            for src in sources:
                path = DATA_DIR / src["file"]
                if not path.exists():
                    continue
                data = json.loads(path.read_text(encoding="utf-8"))
                for book in data.get(src["key"], []):
                    book_id = book.get("id", "")
                    if book_id in id_to_library:
                        duplicates.append(
                            f"{book_id} in both {id_to_library[book_id]} and {library_code}"
                        )
                    else:
                        id_to_library[book_id] = library_code

        hub = self.manifest.get("hub", {})
        _collect(hub.get("code", "hub"), hub.get("sources", []))
        for spoke in self.manifest.get("spokes", []):
            _collect(spoke.get("code", "?"), spoke.get("sources", []))

        if duplicates:
            self._fail("no_duplicate_ids", f"{len(duplicates)} duplicates: {duplicates[:5]}")
        else:
            self._pass("no_duplicate_ids")

    def check_spoke_codes(self) -> None:
        """All spoke codes match known registry partner codes."""
        spoke_codes = {s["code"] for s in self.manifest.get("spokes", [])}
        unknown = spoke_codes - KNOWN_REGISTRY_CODES
        if unknown:
            self._fail("spoke_codes", f"Unknown registry codes: {sorted(unknown)}")
        else:
            self._pass("spoke_codes")

    def check_total(self) -> None:
        """Verify total_network_books matches sum of all library totals."""
        hub = self.manifest.get("hub", {})
        total = hub.get("total_books", 0)
        for spoke in self.manifest.get("spokes", []):
            total += spoke.get("total_books", 0)

        declared = self.manifest.get("total_network_books", 0)
        if total != declared:
            self._fail("total", f"Sum of libraries ({total}) != declared total ({declared})")
        else:
            self._pass("total")

    def run_all(self) -> tuple[int, int, list[str]]:
        """Run all validation checks. Returns (passed, failed, errors)."""
        print(f"Validating manifest: {self.manifest_path}")
        if not self.load():
            return self.passed, self.failed, self.errors

        self.check_schema()
        self.check_batch_coverage()
        self.check_no_duplicate_assignments()
        self.check_counts()
        self.check_no_duplicate_ids()
        self.check_spoke_codes()
        self.check_total()

        print(f"\nResults: {self.passed} passed, {self.failed} failed")
        return self.passed, self.failed, self.errors


def main() -> int:
    """CLI entry point."""
    validator = ManifestValidator()
    passed, failed, errors = validator.run_all()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
