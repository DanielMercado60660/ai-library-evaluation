# Workstream: ADK Agents

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Agent architecture, workflows, and session behavior
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: `docs/development/AGENT_INTEGRATION_GUIDE.md`
- Related Workstream: adk-agents

## Objective
Keep ADK-driven workflows deterministic and observable for benchmark and evaluator usage.

## Current Reality
1. Front desk and specialist agents are implemented with benchmark runner coverage.
2. Run orchestration APIs support async lifecycle and run-indexed artifacts.
3. `v2.1` adds model-aware run metadata and comparison endpoints for evaluator analysis.
4. Assistant route now supports scenario card click-to-run with live trace-backed observability.
5. Assistant runtime is identity-bound to the active evaluator profile with session rotation on patron switches.

## Implemented Footprint
1. Agent services and orchestration:
   - `agents/src/agents/front_desk.py`
   - `agents/src/agents/benchmark_runner.py`
   - `agents/src/agents/benchmark_orchestrator.py`
   - `agents/src/agents/api.py`
2. Comparison/analytics backend primitives:
   - `agents/src/agents/benchmark_api_models.py`
   - `agents/src/agents/benchmark_comparison.py`
   - `agents/src/agents/api.py`
   - `scripts/benchmark_run.py`
3. Coverage:
   - `agents/tests/integration/test_benchmark_runner.py`
   - `agents/tests/integration/test_benchmark_run_lifecycle.py`
   - `agents/tests/integration/test_chat_identity_binding.py`
   - `agents/tests/unit/test_active_patron_tools.py`
   - `agents/tests/integration/test_run_index_integrity.py`
   - `frontend/e2e/assistant-scenario-run.spec.ts`
   - `frontend/e2e/chat-identity.spec.ts`

## Remaining Gaps
1. Multi-provider model adapters beyond Gemini variants (Gemini seam only today).
2. Higher-fidelity tool-call sub-step observability across all runtime components.
3. Operator runbook consolidation for advanced evaluator workflows with identity-switch policy.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: provider adapter boundary expansion for non-Gemini execution.
   - Acceptance checks: adapter conformance tests pass for at least one additional provider.
   - Evidence command(s): `rg -n "build_model_adapter|GeminiModelAdapter|provider" agents/src agents/tests`
2. Owner placeholder: TBD
   - Deliverable: standardized tool-call level audit events for all major agent workflows.
   - Acceptance checks: run traces include per-tool call start/finish and outcome markers.
   - Evidence command(s): `rg -n "TRACE|audit|tool call" agents/src scripts`
3. Owner placeholder: TBD
   - Deliverable: ADK operator runbook update for identity-bound compare/leaderboard lifecycle.
   - Acceptance checks: runbook commands reproduce profile switch + account query + compare flow end-to-end.
   - Evidence command(s): `rg -n "active_patron|session_rebound|benchmark/compare|leaderboard" docs`

## Definition of Done
Agent workflows and benchmark orchestration are deterministic, observable, and reproducible from documented command paths.

## Dependencies
- mcp-tooling
- infrastructure-services
- evaluation-harness

## Risks
- Model nondeterminism obscuring regressions.
- Drift between API contracts and frontend evaluator expectations.
