"""Publication regression: catalog validation must work in a relocated checkout."""

from pathlib import Path
import importlib.util
from unittest.mock import MagicMock

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "validate_catalog.py"
_SPEC = importlib.util.spec_from_file_location("validate_catalog_portability", _SCRIPT)
assert _SPEC is not None and _SPEC.loader is not None
validate_catalog = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(validate_catalog)


def test_validator_uses_relocated_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolve seed data beside the script even when invoked from another cwd."""
    checkout = tmp_path / "cloned-project"
    script = checkout / "scripts" / "validate_catalog.py"
    outside = tmp_path / "unrelated-directory"
    outside.mkdir()
    monkeypatch.chdir(outside)
    monkeypatch.setattr(validate_catalog, "__file__", str(script))
    factory = MagicMock()
    monkeypatch.setattr(validate_catalog, "CatalogValidator", factory)

    validate_catalog.main()

    assert Path(factory.call_args.args[0]) == checkout / "data"
    factory.return_value.load_all_data.assert_called_once()
    factory.return_value.run_all_checks.assert_called_once()
