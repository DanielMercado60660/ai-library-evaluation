# Workstream: A2A Network

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Inter-library agent-to-agent communication and runtime interoperability
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Early A2A planning notes
- Related Workstream: a2a-network

## Objective
Maintain reliable and testable inter-library communication for ILL and federation workflows.

## Current Reality
1. Runtime relay is implemented in registry service and used by ILL workflows.
2. Positive and negative path coverage exists for relay, ack, denial, and retry behavior.
3. Federation integrations now include live spoke validation in ILL request flow.

## Implemented Footprint
1. Registry relay and queue handling:
   - `services/registry/src/registry/a2a_relay.py`
   - `services/registry/src/registry/routes.py`
2. ILL outbound/inbound A2A handling:
   - `services/ill/src/ill/a2a_client.py`
   - `services/ill/src/ill/routes.py`
3. Coverage:
   - `services/ill/tests/integration/test_a2a_happy_path.py`
   - `services/ill/tests/integration/test_a2a_denial_path.py`
   - `services/ill/tests/integration/test_a2a_retry_timeout.py`
   - `services/registry/tests/unit/test_a2a_relay_idempotency.py`

## Remaining Gaps
1. Durable message persistence and replay tooling for long-running outages.
2. Stronger telemetry around queue depth/latency in production-like load.
3. End-to-end contract tests covering larger multi-library topologies.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: relay operational metrics contract (latency, queue depth, retry counts).
   - Acceptance checks: metrics emitted and validated in integration tests.
   - Evidence command(s): `rg -n "a2a|relay|retry|ack" services/registry services/ill`
2. Owner placeholder: TBD
   - Deliverable: durable storage strategy for queued/acked messages.
   - Acceptance checks: restart resilience test proves no message loss for in-flight requests.
   - Evidence command(s): `uv run pytest services/ill/tests services/registry/tests -k a2a -q`
3. Owner placeholder: TBD
   - Deliverable: multi-spoke federation A2A scenario pack.
   - Acceptance checks: scenarios pass under degraded network simulation.
   - Evidence command(s): `uv run pytest tests/scenarios -k "federation or a2a" -q`

## Definition of Done
At least two libraries can exchange and reconcile ILL lifecycle messages with deterministic behavior under normal and degraded conditions.

## Dependencies
- infrastructure-services
- adk-agents
- evaluation-harness

## Risks
- Message-ordering edge cases under concurrent load.
- Privacy leakage if payload validation regresses.
