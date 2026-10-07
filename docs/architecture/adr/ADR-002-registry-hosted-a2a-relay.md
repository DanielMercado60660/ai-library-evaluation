# ADR-002: Registry-Hosted A2A Relay

## Status

Accepted

## Context

The A2A (Agent-to-Agent) protocol needed a message transport for ILL cross-library handoff. The architecture docs (`A2A_PROTOCOL.md`) described a broader JSON-RPC protocol, but the immediate need was a working relay for send/poll/ack message flow between libraries.

Two approaches were considered:

- **Option A (Standalone Broker)**: A dedicated A2A broker service on a separate port (originally planned for 7002). Full JSON-RPC framing with broader protocol semantics.
- **Option B (Registry-Hosted Relay)**: Relay endpoints embedded in the existing registry service on port 8004. Minimal send/poll/ack HTTP API with in-memory message store and deduplication.

## Decision

We chose **Option B (Registry-Hosted Relay)**. The A2A relay endpoints live under `services/registry/src/registry/a2a_relay.py` with routes at `/a2a/message/send`, `/a2a/messages/{library_code}`, and `/a2a/messages/{message_id}/ack`. Message deduplication is handled via `_seen_ids` in the relay store.

Retry behavior is implemented in the ILL service's `a2a_client.py` using exponential backoff with jitter (`services/ill/src/ill/resilience.py`).

## Consequences

**Positive:**
- No additional service to deploy or configure. Simpler Docker Compose and CI.
- Registry already serves as the library directory, so co-locating relay is semantically coherent.
- MVP relay semantics (send/poll/ack) are sufficient for all current benchmark scenarios.

**Trade-offs:**
- Registry service takes on relay responsibility, making it slightly heavier.
- Full JSON-RPC framing from the protocol spec is deferred.
- Migration to a standalone broker remains possible but would require route changes.

**References:** `docs/architecture/A2A_PROTOCOL.md`, `services/registry/src/registry/a2a_relay.py`, `services/registry/src/registry/routes.py`
