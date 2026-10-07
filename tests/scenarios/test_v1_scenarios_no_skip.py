"""Guard test ensuring designated v1 scenarios are runnable (not skip-gated)."""

from pathlib import Path


V1_SCENARIO_FILES = (
    "test_tier1_catalog.py",
    "test_tier2_circulation.py",
    "test_tier3_ill_a2a.py",
    "test_search_flow.py",
    "test_null_content_trap.py",
    "test_honey_pot_redteam.py",
    "test_compliance_report_schema.py",
    "test_safety_pack_scoring.py",
    "test_chaos_fault_injection.py",
    "test_tier3_ill_a2a_chaos.py",
    "test_resilience_scoring.py",
    "test_chaos_report_schema.py",
    "test_federated_seed_manifest.py",
    "test_federated_catalog_partitioning.py",
    "test_ill_network_holdings_resolution.py",
)


def test_v1_scenarios_do_not_contain_skip_controls():
    """v1 scenario files should not rely on skip markers or runtime skips."""
    base = Path(__file__).parent
    violations: list[str] = []

    for filename in V1_SCENARIO_FILES:
        path = base / filename
        content = path.read_text(encoding="utf-8")
        if "@pytest.mark.skip" in content:
            violations.append(f"{filename}: contains @pytest.mark.skip")
        if "pytest.skip(" in content:
            violations.append(f"{filename}: contains pytest.skip(...) call")

    assert not violations, "\n".join(violations)
