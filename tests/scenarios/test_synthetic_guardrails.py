"""Guardrails to ensure scenario tests stay synthetic-world only."""

from pathlib import Path


SCENARIO_DIR = Path(__file__).parent
BANNED_MARKERS = (
    "19" "84",
    "George" " Orwell",
    "Jane" " Austen",
    "Du" "ne",
    "The" " Martian",
    "Project" " Hail Mary",
)


def test_scenarios_contain_no_banned_real_world_markers():
    """Fail when active scenario files reference banned real-world markers."""
    violations: list[str] = []

    for path in sorted(SCENARIO_DIR.glob("test_*.py")):
        if path.name == "test_synthetic_guardrails.py":
            continue

        content = path.read_text(encoding="utf-8")
        for marker in BANNED_MARKERS:
            if marker in content:
                violations.append(f"{path.name}: {marker}")

    assert not violations, "Found banned real-world markers:\n" + "\n".join(violations)
