# Workstream: MCP Tooling

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: MCP resources/tools quality, consistency, and operational reliability
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: early MCP planning notes
- Related Workstream: mcp-tooling

## Objective
Keep MCP tooling consistent with service contracts and reliable for ADK agent workflows.

## Current Reality
1. Core services expose MCP servers and tool/resource endpoints.
2. ADK workflows and benchmark flows rely on MCP-integrated service access.
3. Reliability and auth foundations are in place, but MCP-specific contract governance can be tightened.

## Implemented Footprint
1. Service MCP servers:
   - `services/catalog/src/catalog/mcp_server.py`
   - `services/circulation/src/circulation/mcp_server.py`
   - `services/ill/src/ill/mcp_server.py`
   - `services/registry/src/registry/mcp_server.py`
2. Agent MCP connection management:
   - `agents/src/agents/mcp/`
3. Shared transport/auth helpers:
   - `shared/src/shared/http_client.py`
   - `shared/src/shared/auth.py`

## Remaining Gaps
1. Unified MCP schema/error contract checklist enforced by tests.
2. Cross-service MCP integration matrix for negative-path behavior.
3. Operational guidance for MCP reconnection and degraded-mode handling.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: MCP contract checklist with naming/error conventions.
   - Acceptance checks: all MCP servers pass checklist audit.
   - Evidence command(s): `rg -n "@mcp.tool|@mcp.resource" services/*/src/*/mcp_server.py`
2. Owner placeholder: TBD
   - Deliverable: integration tests spanning catalog/circulation/ILL MCP tool chains.
   - Acceptance checks: positive + negative-path matrix is green.
   - Evidence command(s): `uv run pytest services -k mcp -q`
3. Owner placeholder: TBD
   - Deliverable: MCP lifecycle and troubleshooting runbook.
   - Acceptance checks: runbook linked from ADK workstream docs.
   - Evidence command(s): `rg -n "MCP|connection|lifecycle" docs agents/src`

## Definition of Done
MCP tool/resource contracts are versioned, validated, and operationally documented with deterministic failure behavior.

## Dependencies
- adk-agents
- infrastructure-services

## Risks
- Drift between MCP tool schemas and HTTP API contracts.
- Hidden runtime failures under concurrent tool usage.
