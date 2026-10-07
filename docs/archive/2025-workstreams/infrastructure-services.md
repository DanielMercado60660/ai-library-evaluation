# Workstream: Infrastructure and Services

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Service health, API reliability, and local operator runtime consistency
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: legacy stabilization notes
- Related Workstream: infrastructure-services

## Objective
Keep all core services and operator endpoints reliable for local evaluation and benchmark operations.

## Current Reality
1. Core service mesh is operational (agents/catalog/circulation/ill/registry).
2. Run control plane is implemented and used by frontend routes.
3. `v2.1` APIs (`/benchmark/models`, `/benchmark/compare`, `/benchmark/leaderboard`) are integrated.
4. Assistant click-to-run path is integrated via scenario-scoped run requests and live trace polling.
5. `/chat` contract is identity-aware (`active_patron`, `bound_patron_id`, `session_rebound`) with additive compatibility.

## Implemented Footprint
1. Agents API and orchestration:
   - `agents/src/agents/api.py`
   - `agents/src/agents/chat.py`
   - `agents/src/agents/benchmark_orchestrator.py`
   - `agents/src/agents/run_index.py`
   - `scripts/benchmark_run.py`
   - `agents/src/agents/session/active_patron_context.py`
2. Service-level federation/auth/reliability foundations:
   - `shared/src/shared/auth.py`
   - `shared/src/shared/http_client.py`
   - `shared/src/shared/observability.py`
3. Supporting runtime docs/scripts:
   - `scripts/run_local_alpha.sh`
   - `docker-compose.yml`

## Remaining Gaps
1. Performance tuning pass for frontend and API latency under larger run indexes.
2. More production-like smoke checks for complete multi-service startup health.
3. Optional persisted telemetry store for long-run observability analysis.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: benchmark/chat API smoke suite including identity-bound contracts.
   - Acceptance checks: health + comparison routes + `/chat` identity rotation behavior pass in local and CI smoke jobs.
   - Evidence command(s): `uv run pytest agents/tests/integration -q`
2. Owner placeholder: TBD
   - Deliverable: performance budget checks for analytics-heavy pages.
   - Acceptance checks: build budgets and API response thresholds are documented and enforced.
   - Evidence command(s): `cd frontend && npm run build`
3. Owner placeholder: TBD
   - Deliverable: upgraded runbook for full-stack spin-up + evaluator workflow verification.
   - Acceptance checks: command path reproduces profile switch + account query + run + compare + leaderboard flow.
   - Evidence command(s): `scripts/run_local_alpha.sh`

## Definition of Done
Services start reliably, benchmark APIs remain stable across versions, and operator workflows run end-to-end without manual recovery steps.

## Dependencies
- adk-agents
- evaluation-harness
- mcp-tooling

## Risks
- Local environment drift (ports, tokens, dependency versions).
- API contract regressions during rapid UI iteration.
