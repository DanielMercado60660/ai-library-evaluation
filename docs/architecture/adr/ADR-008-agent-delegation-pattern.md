# ADR-008: Agent Delegation Pattern for v2.1.x

## Status

Accepted

## Context

`docs/architecture/ARCHITECTURE_RECOMMENDATIONS.md` calls out mixed delegation patterns:
- `FrontDeskAgent` class wrapper with function-tool delegation.
- Factory constructors (`create_*_agent`) that can compose specialist agents.

The codebase still relies on `FrontDeskAgent` in session/chat runtime (`agents/src/agents/chat.py`), so removing the class would be a breaking change during active evaluator hardening.

## Decision

Adopt a **compatibility-first delegation standard** for `v2.1.x`:
1. Keep `FrontDeskAgent` class wrapper as the stable runtime entrypoint.
2. Preserve explicit delegation boundaries to specialist agents (catalog, circulation, ILL) inside the front-desk runtime.
3. Keep factory constructors available as migration seams for future full sub-agent composition.
4. Defer class-wrapper removal and strict sub-agent-only runtime to a planned major migration (`v3.0` target).

## Consequences

**Positive:**
- No breaking changes to chat/session orchestration while improving behavior contracts.
- Delegation remains explicit and testable at specialist boundaries.
- Migration path stays open with factory-based seams already present.

**Negative:**
- Temporary coexistence of wrapper and factory patterns increases conceptual overhead.
- Some architectural drift remains until a full sub-agent runtime cutover.

## References

- `docs/architecture/ARCHITECTURE_RECOMMENDATIONS.md`
- `agents/src/agents/front_desk.py`
- `agents/src/agents/chat.py`
- `agents/src/agents/catalog_agent.py`
- `agents/src/agents/circulation_agent.py`
- `agents/src/agents/ill_escalation_agent.py`
