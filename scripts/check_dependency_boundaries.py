"""Dependency boundary checker using Python AST import analysis.

Scans source directories and verifies no forbidden cross-layer imports exist.
Rules are defined in BOUNDARY_RULES and enforced by CI.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Maps source directories to their forbidden import module prefixes.
# Key: directory relative to PROJECT_ROOT to scan.
# Value: set of top-level module names that must NOT appear in imports.
BOUNDARY_RULES: dict[str, set[str]] = {
    "shared/src/shared": {"agents", "catalog", "circulation", "ill", "registry"},
    "services/catalog/src": {"agents", "circulation", "ill", "registry"},
    "services/circulation/src": {"agents", "catalog", "ill", "registry"},
    "services/ill/src": {"agents", "catalog", "circulation", "registry"},
    "services/registry/src": {"agents", "catalog", "circulation", "ill"},
    "agents/src": {"catalog", "circulation", "ill", "registry"},
}


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
    """Parse a Python file and return (line_number, module_name) for all imports."""
    try:
        tree = ast.parse(filepath.read_text(encoding="utf-8"), filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            # Only check absolute imports (level == 0).
            # Relative imports (from .db import ...) are always allowed.
            if node.module and node.level == 0:
                imports.append((node.lineno, node.module))
    return imports


def _top_level_module(module_name: str) -> str:
    """Extract the top-level package name from a dotted module path."""
    return module_name.split(".")[0]


class BoundaryChecker:
    """Validates dependency boundaries across project layers."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.violations: list[str] = []
        self.files_scanned = 0

    def check_directory(self, rel_dir: str, forbidden: set[str]) -> None:
        """Scan all .py files under rel_dir for forbidden imports."""
        src_dir = self.project_root / rel_dir
        if not src_dir.exists():
            return

        for py_file in sorted(src_dir.rglob("*.py")):
            self.files_scanned += 1
            for lineno, module_name in _extract_imports(py_file):
                top = _top_level_module(module_name)
                if top in forbidden:
                    rel_path = py_file.relative_to(self.project_root)
                    self.violations.append(
                        f"{rel_path}:{lineno}: imports '{module_name}' "
                        f"(forbidden: {top} not allowed in {rel_dir})"
                    )

    def run_all(self) -> list[str]:
        """Run boundary checks for all configured rules."""
        print(f"Scanning dependency boundaries in: {self.project_root}")
        for rel_dir, forbidden in BOUNDARY_RULES.items():
            self.check_directory(rel_dir, forbidden)

        if self.violations:
            print(f"\nBOUNDARY VIOLATIONS ({len(self.violations)}):")
            for v in self.violations:
                print(f"  {v}")
        else:
            print("\nNo violations found.")

        print(f"Files scanned: {self.files_scanned}")
        return self.violations


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Check dependency boundary rules.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on violations")
    args = parser.parse_args()

    checker = BoundaryChecker()
    violations = checker.run_all()

    if args.strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
