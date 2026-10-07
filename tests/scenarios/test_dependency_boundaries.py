"""Tests for dependency boundary enforcement."""

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from check_dependency_boundaries import (  # noqa: E402
    BOUNDARY_RULES,
    BoundaryChecker,
    _extract_imports,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class TestDependencyBoundaries:
    """Verify boundary rules and checker behavior."""

    def test_current_codebase_passes_all_boundaries(self):
        """The entire current codebase has no boundary violations."""
        checker = BoundaryChecker(project_root=PROJECT_ROOT)
        violations = checker.run_all()
        assert not violations, (
            f"Boundary violations found:\n" + "\n".join(violations)
        )

    def test_checker_catches_forbidden_import(self, tmp_path):
        """A synthetic file with a forbidden import is detected."""
        fake_root = tmp_path / "project"
        fake_shared = fake_root / "shared" / "src" / "shared"
        fake_shared.mkdir(parents=True)
        violation_file = fake_shared / "bad_module.py"
        violation_file.write_text("from catalog.models import BookModel\n")

        checker = BoundaryChecker(project_root=fake_root)
        checker.check_directory("shared/src/shared", {"catalog"})

        assert len(checker.violations) == 1
        assert "catalog" in checker.violations[0]
        assert "bad_module.py" in checker.violations[0]

    def test_relative_imports_are_not_flagged(self, tmp_path):
        """Relative imports within a package are allowed."""
        fake_root = tmp_path / "project"
        fake_catalog = fake_root / "services" / "catalog" / "src"
        fake_catalog.mkdir(parents=True)
        ok_file = fake_catalog / "internal.py"
        ok_file.write_text("from .db import get_session\n")

        checker = BoundaryChecker(project_root=fake_root)
        checker.check_directory("services/catalog/src", {"agents", "circulation"})

        assert not checker.violations

    def test_scripts_and_tests_are_exempted(self):
        """Scripts and tests directories are not scanned by boundary rules."""
        for key in BOUNDARY_RULES:
            assert not key.startswith("scripts"), f"scripts should be exempted: {key}"
            assert not key.startswith("tests"), f"tests should be exempted: {key}"

    def test_extract_imports_handles_syntax_error(self, tmp_path):
        """Files with syntax errors are skipped gracefully."""
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def broken(\n")
        result = _extract_imports(bad_file)
        assert result == []
