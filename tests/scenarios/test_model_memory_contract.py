"""Model and memory contract tests for v2.0.

Enforces ADR-005 (single-provider Gemini) and ADR-006 (session-only memory)
constraints. These tests prevent accidental drift toward multi-provider or
persistent memory code before v2.1.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_SRC = PROJECT_ROOT / "agents" / "src" / "agents"
ADR_DIR = PROJECT_ROOT / "docs" / "architecture" / "adr"


class TestModelProviderContract:
    """Enforce ADR-005: single-provider Gemini model contract."""

    def test_model_name_defaults_to_gemini_flash(self):
        """config.py defaults MODEL_NAME to gemini-3-flash-preview."""
        config_source = (AGENTS_SRC / "config.py").read_text(encoding="utf-8")
        assert '"gemini-3-flash-preview"' in config_source, (
            "MODEL_NAME default must be gemini-3-flash-preview"
        )

    def test_no_model_provider_env_var(self):
        """config.py has no MODEL_PROVIDER configuration."""
        config_source = (AGENTS_SRC / "config.py").read_text(encoding="utf-8")
        assert "MODEL_PROVIDER" not in config_source, (
            "MODEL_PROVIDER env var must not exist in v2.0 (ADR-005)"
        )

    def test_adk_runtime_uses_inmemory_runner(self):
        """adk_runtime.py uses InMemoryRunner."""
        runtime_source = (
            AGENTS_SRC / "utils" / "adk_runtime.py"
        ).read_text(encoding="utf-8")
        assert "InMemoryRunner" in runtime_source, (
            "adk_runtime must use InMemoryRunner (ADR-005)"
        )

    def test_adk_runtime_accepts_llm_agent(self):
        """run_agent_text signature accepts an agent parameter."""
        runtime_source = (
            AGENTS_SRC / "utils" / "adk_runtime.py"
        ).read_text(encoding="utf-8")
        assert "agent:" in runtime_source or "agent=" in runtime_source, (
            "run_agent_text must accept an agent parameter"
        )


class TestMemoryContract:
    """Enforce ADR-006: session-only memory contract."""

    def test_adk_runtime_sets_auto_create_session(self):
        """adk_runtime.py sets auto_create_session = True."""
        runtime_source = (
            AGENTS_SRC / "utils" / "adk_runtime.py"
        ).read_text(encoding="utf-8")
        assert "auto_create_session = True" in runtime_source, (
            "adk_runtime must set auto_create_session = True (ADR-006)"
        )

    def test_no_persistent_memory_imports_in_agents(self):
        """No persistent memory classes are imported in agent modules."""
        forbidden = ["firestore", "EpisodicMemory", "SemanticMemory"]
        agent_files = list(AGENTS_SRC.glob("*.py"))
        assert agent_files, "Expected agent source files in agents/src/agents/"

        violations = []
        for f in agent_files:
            source = f.read_text(encoding="utf-8")
            for term in forbidden:
                if term in source:
                    violations.append(f"{f.name}: contains '{term}'")

        assert not violations, (
            f"Persistent memory imports found (ADR-006 violation): {violations}"
        )

    def test_adr_005_exists_and_accepted(self):
        """ADR-005 exists and has Accepted status."""
        adr = ADR_DIR / "ADR-005-single-provider-model-contract.md"
        assert adr.exists(), f"Missing {adr}"
        content = adr.read_text(encoding="utf-8")
        assert "Accepted" in content, "ADR-005 must have Accepted status"

    def test_adr_006_exists_and_accepted(self):
        """ADR-006 exists and has Accepted status."""
        adr = ADR_DIR / "ADR-006-session-only-memory-contract.md"
        assert adr.exists(), f"Missing {adr}"
        content = adr.read_text(encoding="utf-8")
        assert "Accepted" in content, "ADR-006 must have Accepted status"
