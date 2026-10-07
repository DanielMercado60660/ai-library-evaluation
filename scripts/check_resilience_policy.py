"""Resilience policy checker using Python AST analysis.

Scans agent tool files for async functions that create httpx.AsyncClient
and verifies each is decorated with @with_retry. Enforced in CI.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Directories to scan for resilience policy compliance.
TOOL_DIRS = [
    "agents/src/agents/tools",
]


def _has_with_retry_decorator(func_node: ast.AsyncFunctionDef) -> bool:
    """Check if an async function has @with_retry among its decorators."""
    for deco in func_node.decorator_list:
        # @with_retry or @with_retry(...)
        if isinstance(deco, ast.Name) and deco.id == "with_retry":
            return True
        if isinstance(deco, ast.Call):
            func = deco.func
            if isinstance(func, ast.Name) and func.id == "with_retry":
                return True
            if isinstance(func, ast.Attribute) and func.attr == "with_retry":
                return True
    return False


def _uses_httpx_async_client(func_node: ast.AsyncFunctionDef) -> bool:
    """Check if an async function body contains httpx.AsyncClient usage."""
    for node in ast.walk(func_node):
        # Match httpx.AsyncClient() call
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "AsyncClient":
                if isinstance(func.value, ast.Name) and func.value.id == "httpx":
                    return True
    return False


class ResiliencePolicyChecker:
    """Validates that agent tool functions using httpx have @with_retry."""

    def __init__(self, project_root: Path = PROJECT_ROOT) -> None:
        self.project_root = project_root
        self.violations: list[str] = []
        self.files_scanned = 0

    def check_directory(self, rel_dir: str) -> None:
        """Scan all .py files under rel_dir for policy violations."""
        src_dir = self.project_root / rel_dir
        if not src_dir.exists():
            return

        for py_file in sorted(src_dir.rglob("*.py")):
            if py_file.name.startswith("__"):
                continue
            self.files_scanned += 1
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if not isinstance(node, ast.AsyncFunctionDef):
                    continue
                if _uses_httpx_async_client(node) and not _has_with_retry_decorator(node):
                    rel_path = py_file.relative_to(self.project_root)
                    self.violations.append(
                        f"{rel_path}:{node.lineno}: function '{node.name}' "
                        f"uses httpx.AsyncClient without @with_retry"
                    )

    def run_all(self) -> list[str]:
        """Run resilience policy checks for all configured directories."""
        print(f"Scanning resilience policy in: {self.project_root}")
        for rel_dir in TOOL_DIRS:
            self.check_directory(rel_dir)

        if self.violations:
            print(f"\nRESILIENCE POLICY VIOLATIONS ({len(self.violations)}):")
            for v in self.violations:
                print(f"  {v}")
        else:
            print("\nNo violations found.")

        print(f"Files scanned: {self.files_scanned}")
        return self.violations


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Check resilience policy rules.")
    parser.add_argument("--strict", action="store_true", help="Non-zero exit on violations")
    args = parser.parse_args()

    checker = ResiliencePolicyChecker()
    violations = checker.run_all()

    if args.strict and violations:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
