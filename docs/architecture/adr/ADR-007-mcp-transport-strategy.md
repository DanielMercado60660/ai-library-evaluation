# ADR-007: MCP Transport Strategy for v2.1.x

## Status

Accepted

## Context

`docs/architecture/ARCHITECTURE_RECOMMENDATIONS.md` recommends clarifying MCP-vs-HTTP tool transport and potentially moving to MCP-first with SSE support. Current runtime behavior in `v2.1` is:
- Hot-path agent tools use direct HTTP service calls (`agents/src/agents/tools/*.py`).
- MCP servers exist in services for compatibility and future integration.
- Assistant evaluator workflows (scenario click-to-run, live audit stream) currently depend on HTTP tool stability and low setup overhead.

A full MCP-first migration in this increment would add transport/runtime risk to identity binding and benchmark UX closure work.

## Decision

For `v2.1.x`, keep **HTTP-first** transport for agent hot paths and treat MCP as a prepared integration surface:
1. HTTP tools remain the default execution path for catalog/circulation/ILL in agents.
2. MCP servers remain supported but are not the primary runtime path.
3. SSE transport rollout is deferred until a dedicated migration slice (`v2.2+`) with parity tests.
4. Any new tool contract in `v2.1.x` must be representable in both HTTP and MCP schemas to avoid lock-in.

## Consequences

**Positive:**
- Preserves benchmark reliability and evaluator UX while shipping identity-bound assistant behavior.
- Avoids introducing MCP transport instability during active scenario/evaluation iteration.
- Keeps migration option open by enforcing schema parity discipline.

**Negative:**
- Duplicate transport surfaces continue in the short term.
- Full MCP-first operational benefits (tool discovery, transport unification) are delayed.

## References

- `docs/architecture/ARCHITECTURE_RECOMMENDATIONS.md`
- `agents/src/agents/tools/catalog_tools.py`
- `agents/src/agents/tools/circulation_tools.py`
- `agents/src/agents/tools/ill_tools.py`
