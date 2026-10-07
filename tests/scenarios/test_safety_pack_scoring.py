"""Safety pack scoring integration tests for benchmark report v1.2."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from benchmark_run import ManifestScenario, load_manifest  # noqa: E402


MANIFEST_PATH = Path(__file__).resolve().parents[2] / "tests" / "scenarios" / "scenario_manifest.json"


class TestManifestSafetyFields:
    """Validate that manifest supports v1.2 safety pack fields."""

    def test_manifest_loads_safety_pack_field(self):
        """ManifestScenario accepts optional safety_pack field."""
        scenario = ManifestScenario(
            scenario_id="test_safety",
            nodeid_pattern="test_null_content",
            tier=1,
            expected_steps=2,
            policy_checks=1,
            tool_calls_total=1,
            taxonomy_hint="content_fabrication",
            safety_pack="null_content",
            expected_refusal=True,
        )
        assert scenario.safety_pack == "null_content"
        assert scenario.expected_refusal is True

    def test_manifest_defaults_for_safety_fields(self):
        """Safety fields default to None/False when not provided."""
        scenario = ManifestScenario(
            scenario_id="test_legacy",
            nodeid_pattern="test_tier1",
            tier=1,
            expected_steps=1,
            policy_checks=1,
            tool_calls_total=1,
            taxonomy_hint=None,
        )
        assert scenario.safety_pack is None
        assert scenario.expected_refusal is False
        assert scenario.canary_tags is None
        assert scenario.attack_type is None

    def test_manifest_backward_compat_with_v1_entries(self):
        """Existing v1 manifest entries parse without error."""
        entries = load_manifest(MANIFEST_PATH)
        assert len(entries) > 0
        # All existing entries should have safety_pack=None.
        for entry in entries:
            if entry.safety_pack is None:
                continue
            # If any have safety_pack set, it must be a valid value.
            assert entry.safety_pack in ("null_content", "honey_pot")

    def test_manifest_safety_scenarios_present(self):
        """Manifest includes v1.2 safety pack scenario entries."""
        entries = load_manifest(MANIFEST_PATH)
        safety_entries = [e for e in entries if e.safety_pack is not None]
        assert len(safety_entries) >= 2, (
            "Expected at least 2 safety pack scenarios in manifest"
        )
        packs = {e.safety_pack for e in safety_entries}
        assert "null_content" in packs
        assert "honey_pot" in packs
