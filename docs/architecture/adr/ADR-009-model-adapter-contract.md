# ADR-009: Model Adapter Contract for v2.1.x

## Status

Accepted

## Context

`v2.1` introduces model-aware benchmark runs and comparison surfaces. The architecture recommendations call for a provider abstraction layer, but current runtime remains Gemini-only and ADK-native. Prior to this ADR, model selection logic was spread across agents and run orchestration.

To reduce drift and prepare for future providers without destabilizing the current evaluator loop, a lightweight adapter seam was added:
- `agents/src/agents/models/base.py`
- `agents/src/agents/models/gemini_adapter.py`
- `agents/src/agents/models/factory.py`

## Decision

Adopt a **minimal adapter contract** for `v2.1.x`:
1. Runtime model resolution goes through `build_model_adapter()` factory.
2. Adapter contract for this phase is ADK-compatible model reference emission (`to_adk_model_ref()`), not full provider SDK abstraction.
3. Gemini is the only shipped adapter in `v2.1.x`.
4. New providers must implement the same contract and be wired through the factory without breaking existing Gemini defaults.

## Consequences

**Positive:**
- Centralized model resolution and reduced direct config coupling in agents.
- Enables incremental provider expansion without immediate broad refactor.
- Keeps current Gemini flows stable and backward compatible.

**Negative:**
- Contract is intentionally narrow and not yet a full cross-provider execution abstraction.
- Additional provider-specific capabilities (streaming/tool quirks) remain future work.

## References

- `docs/architecture/ARCHITECTURE_RECOMMENDATIONS.md`
- `agents/src/agents/models/base.py`
- `agents/src/agents/models/gemini_adapter.py`
- `agents/src/agents/models/factory.py`
- `agents/src/agents/front_desk.py`
- `agents/src/agents/circulation_agent.py`
- `agents/src/agents/ill_escalation_agent.py`
