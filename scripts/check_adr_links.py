"""Validator for ADR index/file consistency.

Ensures every ADR file in docs/architecture/adr/ is indexed,
every INDEX.md entry has a corresponding file, and each ADR
has the required sections.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ADR_DIR = Path(__file__).resolve().parent.parent / "docs" / "architecture" / "adr"

REQUIRED_SECTIONS = {"## Status", "## Context", "## Decision", "## Consequences"}


class ADRLinkChecker:
    """Validates ADR governance artifacts."""

    def __init__(self, adr_dir: Path = ADR_DIR) -> None:
        self.adr_dir = adr_dir
        self.index_path = adr_dir / "INDEX.md"
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

    def _adr_files_on_disk(self) -> set[str]:
        """Return set of ADR filenames matching ADR-*.md pattern."""
        return {f.name for f in self.adr_dir.glob("ADR-*.md")}

    def _adr_files_in_index(self) -> set[str]:
        """Parse INDEX.md and return set of referenced ADR filenames."""
        if not self.index_path.exists():
            return set()
        text = self.index_path.read_text(encoding="utf-8")
        return set(re.findall(r"\((ADR-\d+[^)]*\.md)\)", text))

    def check_index_exists(self) -> bool:
        """Verify INDEX.md exists."""
        if not self.index_path.exists():
            self._fail("index_exists", f"INDEX.md not found at {self.index_path}")
            return False
        self._pass("index_exists")
        return True

    def check_all_files_indexed(self) -> None:
        """Verify every ADR file on disk is listed in INDEX.md."""
        on_disk = self._adr_files_on_disk()
        in_index = self._adr_files_in_index()
        # Exclude the template from the check
        on_disk.discard("ADR_TEMPLATE.md")
        unindexed = on_disk - in_index
        if unindexed:
            self._fail("all_files_indexed", f"ADR files not in INDEX.md: {sorted(unindexed)}")
        else:
            self._pass("all_files_indexed")

    def check_all_index_entries_exist(self) -> None:
        """Verify every INDEX.md entry has a corresponding file."""
        on_disk = self._adr_files_on_disk()
        in_index = self._adr_files_in_index()
        missing = in_index - on_disk
        if missing:
            self._fail("all_index_entries_exist", f"INDEX.md refs missing files: {sorted(missing)}")
        else:
            self._pass("all_index_entries_exist")

    def check_required_sections(self) -> None:
        """Verify each ADR file has all required sections."""
        for adr_file in sorted(self._adr_files_on_disk()):
            if adr_file == "ADR_TEMPLATE.md":
                continue
            text = (self.adr_dir / adr_file).read_text(encoding="utf-8")
            missing = [s for s in REQUIRED_SECTIONS if s not in text]
            if missing:
                self._fail(f"sections({adr_file})", f"Missing sections: {missing}")
            else:
                self._pass(f"sections({adr_file})")

    def run_all(self) -> tuple[int, int, list[str]]:
        """Run all validation checks. Returns (passed, failed, errors)."""
        print(f"Validating ADR governance: {self.adr_dir}")
        if not self.check_index_exists():
            return self.passed, self.failed, self.errors
        self.check_all_files_indexed()
        self.check_all_index_entries_exist()
        self.check_required_sections()
        print(f"\nResults: {self.passed} passed, {self.failed} failed")
        return self.passed, self.failed, self.errors


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Validate ADR governance artifacts.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on violations")
    args = parser.parse_args()

    checker = ADRLinkChecker()
    _passed, failed, _errors = checker.run_all()

    if args.strict and failed > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
