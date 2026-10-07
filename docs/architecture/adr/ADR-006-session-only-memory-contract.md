# ADR-006: Session-Only Memory Contract for v2.0

## Status

Accepted

## Context

The `docs/architecture/MEMORY_SYSTEM.md` document describes a comprehensive three-tier memory architecture (working → episodic → semantic) with Firestore/Cloud SQL storage, Vertex AI embeddings, consent management, and patron profile levels. This is valuable future work for cross-session patron evaluation (`v2.1+`), but for v2.0 Local Hosted Alpha the system uses Google ADK's `InMemoryRunner` with session-scoped state only.

Current implementation:
- `agents/src/agents/utils/adk_runtime.py`: `InMemoryRunner(agent=agent, app_name=app_name)` with `runner.auto_create_session = True`
- Session state lives in the `InMemoryRunner` process memory
- No `EpisodicMemory`, no `SemanticMemory`, no `FirestoreMemoryStore` exists in code
- No consent management, no patron profile levels, no embedding generation
- Session state is lost on process restart

Building a full memory persistence layer before validating the evaluation methodology through local alpha usage would be premature optimization.

## Decision

v2.0 ships with session-only memory via `InMemoryRunner`. There is no episodic memory, no semantic memory, no persistence across sessions, and no consent management. Session state is scoped to the lifetime of the runner process and the session ID. `MEMORY_SYSTEM.md` remains as a Planned roadmap document for `v2.1+`.

The v2.0 memory contract is:
1. `InMemoryRunner` is the sole execution runtime
2. `auto_create_session = True` enables automatic session management
3. No persistent memory store exists (no Firestore, no Cloud SQL for memory)
4. No `EpisodicMemory` or `SemanticMemory` classes are imported in agent code
5. No consent management or patron profile levels are implemented
6. Session state is lost on process restart — this is intentional for alpha

Contract tests in `tests/scenarios/test_model_memory_contract.py` enforce these constraints.

## Consequences

**Positive:**
- Reduces v2.0 scope to focus on operator workflow validation
- Prevents premature abstraction of memory tiers before evaluation methodology is proven
- Avoids infrastructure dependencies (Firestore, Vertex AI) for local alpha
- Contract tests catch accidental drift toward persistent memory code

**Negative:**
- Cannot test cross-session recall or preference learning until `v2.1+`
- `MEMORY_SYSTEM.md` remains aspirational
- Each benchmark run starts with a fresh agent memory state

## References

- `docs/architecture/MEMORY_SYSTEM.md` (Doc Status: Planned)
- `agents/src/agents/utils/adk_runtime.py`
- `tests/scenarios/test_model_memory_contract.py`
