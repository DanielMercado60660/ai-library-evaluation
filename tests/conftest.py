"""Pytest configuration and fixtures."""

import pytest
import asyncio
import json
import os
from pathlib import Path
from typing import Generator

_TRACE_ENABLED_ENV = "BENCHMARK_TRACE_ENABLED"
_ACTIVE_SCENARIO_ENV = "BENCHMARK_ACTIVE_SCENARIO_ID"
_MANIFEST_PATH = Path(__file__).resolve().parent / "scenarios" / "scenario_manifest.json"

_SCENARIO_MATCHERS: list[tuple[str, str]] | None = None


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Inject active scenario id for runtime trace emission during benchmark runs."""
    if not _runtime_trace_enabled():
        return
    os.environ[_ACTIVE_SCENARIO_ENV] = _resolve_scenario_id(item.nodeid)


def pytest_runtest_teardown(item: pytest.Item) -> None:  # noqa: ARG001
    """Clear active scenario marker after each test."""
    if not _runtime_trace_enabled():
        return
    os.environ.pop(_ACTIVE_SCENARIO_ENV, None)


def _runtime_trace_enabled() -> bool:
    token = os.getenv(_TRACE_ENABLED_ENV, "").strip().lower()
    return token in {"1", "true", "yes", "on"}


def _resolve_scenario_id(nodeid: str) -> str:
    """Map pytest nodeid to manifest scenario id when available."""
    entries = _load_scenario_matchers()
    matches = [entry for entry in entries if entry[0] in nodeid]
    if not matches:
        return nodeid
    return sorted(matches, key=lambda entry: len(entry[0]), reverse=True)[0][1]


def _load_scenario_matchers() -> list[tuple[str, str]]:
    """Load (nodeid_pattern, scenario_id) mappings from scenario manifest."""
    global _SCENARIO_MATCHERS
    if _SCENARIO_MATCHERS is not None:
        return _SCENARIO_MATCHERS

    if not _MANIFEST_PATH.exists():
        _SCENARIO_MATCHERS = []
        return _SCENARIO_MATCHERS

    payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    scenarios = payload.get("scenarios", [])
    _SCENARIO_MATCHERS = [
        (str(entry.get("nodeid_pattern", "")), str(entry.get("id", "")))
        for entry in scenarios
        if entry.get("nodeid_pattern") and entry.get("id")
    ]
    return _SCENARIO_MATCHERS
