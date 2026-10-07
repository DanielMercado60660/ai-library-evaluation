# v2.1 Execution Plan: Comparison Analytics + Assistant Scenario Click-to-Run

## Doc Header
- Doc Status: Completed
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Delivery plan for `v2.1` comparison analytics, model-aware runs, assistant click-to-run execution, identity-bound assistant behavior, and evaluator UX polish
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Ad-hoc `v2.1` notes in chat
- Related Workstream: infrastructure-services, adk-agents, evaluation-harness, world-data-governance

## Summary
This plan delivers a complete `v2.1` increment focused on evaluator-facing comparison workflows and live scenario observability:
1. Add model-aware run metadata (`model_name`, `model_family`) for comparable run records.
2. Ship both comparison surfaces: run-to-run deltas and model leaderboard aggregation.
3. Restore analytics as a dedicated route (`/#/analytics`) available to all evaluator patrons.
4. Enable assistant scenario card click-to-run with scenario-scoped pytest execution.
5. Stream live audit events in the Assistant panel, including tool-call and step-level events.
6. Keep direct-replace rollout with backward compatibility for historical run artifacts.
7. Reconcile status/workstream docs so implementation and roadmap stay aligned.
8. Bind assistant account actions to active evaluator profile context (no patron-ID prompt when context exists).
9. Add v2.2-prep seams (ADR closure + model adapter/runtime standardization scaffolding) without breaking v2.1 behavior.

## Scope
### In Scope
1. Backend comparison APIs and deterministic scoring/aggregation.
2. Frontend analytics UX, deep-link compare flows, and model selection in run config.
3. Role-aligned access (analytics for all evaluator patrons; patron directory remains staff-only).
4. Assistant scenario click-to-run flow (script replay + scenario-scoped benchmark run).
5. Live Assistant audit stream wiring from `GET /benchmark/runs/{run_id}/trace`.
6. Account-switch discoverability via top-bar quick switch.
7. Status/workstream documentation reconciliation.
8. Backend + frontend automated tests for new contracts and flows.

### Out of Scope
1. Multi-provider adapters (OpenAI/Anthropic/Ollama).
2. Hosted/public leaderboard service.
3. Billing/entitlements.
4. RL export/data-product pipeline.

## Public API / Interface / Type Contract

### Backend API additions and changes
1. `POST /benchmark/runs` request now supports optional `model_name`.
2. `POST /benchmark/runs` request now supports optional:
   - `scenario_ids: list[str] | null` (scenario-scoped execution)
   - `trigger_source: str | null` (for evaluator UI attribution)
3. `RunMetadata` now includes additive fields:
   - `model_name: str` (default `"unknown"` for legacy records)
   - `model_family: str` (default `"gemini"`)
   - `scenario_ids: list[str]` (default `[]`)
   - `trigger_source: str` (default `"manual"`)
4. New `GET /benchmark/models` endpoint:
   - returns available Gemini variants and default model.
5. New `POST /benchmark/compare` endpoint:
   - input: `run_ids` (2-5), optional `suite`
   - output: run snapshots, run deltas, tier deltas, scenario deltas, ranked ordering.
6. New `GET /benchmark/leaderboard` endpoint:
   - query: `suite?`, `limit` (default 20), `min_runs` (default 1)
   - output: model-level aggregate ranking rows with deterministic ordering.
7. Existing `v1.5` run/report/trace routes remain unchanged.
8. `POST /chat` accepts additive optional `active_patron` payload:
   - `id: str`, `name: str | null`, `role: "patron" | "staff" | null`
9. `POST /chat` response includes additive fields:
   - `bound_patron_id: str | null`
   - `session_rebound: bool`
10. `POST /benchmark/runs` request/response/index now include additive optional:
   - `actor_patron_id: str | null`

### Frontend additions and changes
1. `frontend/src/app/shared/models/benchmark.models.ts` adds:
   - `ModelCatalogResponse`
   - `RunComparisonRequest`, `RunComparisonResponse`
   - `LeaderboardResponse`
   - additive run metadata: `model_name`, `model_family`
2. `frontend/src/app/core/services/run.service.ts` adds:
   - `getModels()`
   - `compareRuns()`
   - `getLeaderboard()`
3. `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts` adds model dropdown sourced from `GET /benchmark/models` and sends `model_name` in run create payload.
4. Assistant orchestration additions:
   - `frontend/src/app/core/services/assistant-run.service.ts` for active run focus, status/trace polling, and script triggers
   - additive run fields in `frontend/src/app/shared/models/benchmark.models.ts`: `scenario_ids`, `trigger_source`
   - shared audit mapper `frontend/src/app/shared/utils/audit-trace.mapper.ts` used by both run detail and assistant forensic ledger
5. Chat/session identity additions:
   - `frontend/src/app/core/services/chat.service.ts` sends `active_patron` on every chat message
   - `frontend/src/app/core/services/chat.service.ts` consumes `bound_patron_id` and `session_rebound`
   - profile and top-bar patron switching now prompt for `fresh` vs `keep` transcript behavior

## Scoring and Ranking Rules
1. Comparison/leaderboard include completed runs only: `status in passed|failed`.
2. Composite formula per run:
   - `completion_norm = completion_rate_percent / 100`
   - `policy_norm = policy_compliance_percent / 100`
   - `tool_norm = tool_precision_percent / 100`
   - `hallucination_penalty = min(hallucinations / max(total, 1), 1)`
   - `composite_score = 100 * (0.35*completion_norm + 0.25*policy_norm + 0.25*tool_norm + 0.15*(1 - hallucination_penalty))`
3. Leaderboard grouping key: `model_name`.
4. Leaderboard deterministic sort order:
   - `avg_composite_score DESC`
   - `avg_policy_compliance DESC`
   - `avg_tool_precision DESC`
   - `avg_hallucinations ASC`
   - `model_name ASC`

## Implementation Footprint

### Backend
- `agents/src/agents/benchmark_api_models.py`
- `agents/src/agents/benchmark_orchestrator.py`
- `agents/src/agents/benchmark_comparison.py` (new)
- `agents/src/agents/api.py`
- `agents/src/agents/chat.py`
- `agents/src/agents/session/active_patron_context.py` (new)
- `agents/src/agents/session/adk_session_service.py`
- `agents/src/agents/tools/circulation_tools.py`
- `agents/src/agents/tools/ill_tools.py`
- `agents/src/agents/models/base.py` (new)
- `agents/src/agents/models/gemini_adapter.py` (new)
- `agents/src/agents/models/factory.py` (new)
- `scripts/benchmark_run.py`
- `tests/fixtures/golden/run-index-v1.5.json`

### Frontend
- `frontend/src/app/shared/models/benchmark.models.ts`
- `frontend/src/app/core/services/run.service.ts`
- `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts`
- `frontend/src/app/features/analytics/analytics.component.ts` (new)
- `frontend/src/app/core/services/assistant-run.service.ts` (new)
- `frontend/src/app/core/services/chat.service.ts`
- `frontend/src/app/shared/utils/audit-trace.mapper.ts` (new)
- `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts`
- `frontend/src/app/features/chat/chat.component.ts`
- `frontend/src/app/features/forensic-ledger/forensic-ledger.component.ts`
- `frontend/src/app/features/runs/run-list.component.ts`
- `frontend/src/app/features/run-detail/run-detail.component.ts`
- `frontend/src/app/core/layout/main-layout.component.ts`
- `frontend/src/app/features/profile/patron-profile.component.ts`
- `frontend/src/app/app.routes.ts`
- `frontend/e2e/analytics.spec.ts` (new)
- `frontend/e2e/assistant-scenario-run.spec.ts` (new)
- `frontend/e2e/chat-identity.spec.ts` (new)

### Tests
- `agents/tests/integration/test_benchmark_run_lifecycle.py`
- `agents/tests/integration/test_chat_identity_binding.py` (new)
- `agents/tests/integration/test_run_index_integrity.py`
- `agents/tests/integration/test_session_persistence.py`
- `agents/tests/unit/test_active_patron_tools.py` (new)
- `tests/scenarios/test_contract_compatibility.py`

## Execution Sequence

### Phase 1: Backend model-aware run contract
1. Add additive model metadata to run request/response/index models.
2. Persist selected model in orchestrator and pass per-run `MODEL_NAME` to subprocess.
3. Add additive scenario-scoped metadata (`scenario_ids`, `trigger_source`) in run request/response/index models.
4. Forward scenario ids to benchmark runner as repeated `--scenario-id` CLI args.
5. Update benchmark runner to support scenario-id filtering and report/trace metadata (`selected_scenario_ids`).
6. Keep run-index loading backward compatible; no migration required.

### Phase 2: Comparison and leaderboard APIs
1. Introduce deterministic aggregation module for scoring, deltas, and ordering.
2. Implement `POST /benchmark/compare` validation and payload generation.
3. Implement `GET /benchmark/leaderboard` with deterministic sort.
4. Implement `GET /benchmark/models` from env catalog with fallback defaults.

### Phase 3: Dedicated analytics route and direct-replace UX
1. Add `/analytics` feature route and nav entry.
2. Build analytics page sections: run compare workbench, delta tables, leaderboard.
3. Support deep-link prefill with `runs=runA,runB,...` query param.
4. Add compare entry points from run list and run detail views.

### Phase 4: Assistant scenario click-to-run and live audit stream
1. Scenario card click in Assistant performs `select + run immediately` for the clicked scenario.
2. Card-triggered run posts `suite="scenarios"`, `scenario_ids=[clicked_id]`, `trigger_source="assistant_card"`.
3. Assistant chat resets and replays scenario script while run executes asynchronously.
4. Forensic ledger consumes live run trace events and renders tool-call/step lifecycle updates in real time.
5. Forensic ledger includes direct deep-link to run detail page (`/#/runs/:runId`) while live run focus is active.

### Phase 5: Role UX and account-switch polish
1. Keep analytics/comparison accessible for all evaluator patrons.
2. Keep patron directory as staff-only route.
3. Add top-bar quick patron switch while keeping My Account switcher.

### Phase 6: Documentation reconciliation
1. Create this `V2_1_EXECUTION_PLAN.md` contract.
2. Update `PROJECT_STATUS.md` with implementation/evidence.
3. Update `VERSION_LADDER_PROPOSAL.md` to mark `v2.1` as in progress.
4. Refresh stale workstream docs to current state and next milestones.

### Phase 7: Identity-bound assistant + v2.2 prep seams
1. `/chat` request binds active patron context to backend session state and runtime contextvars.
2. Session manager rotates backend session when active patron changes (`session_rebound=true`).
3. Circulation/ILL self-tools resolve identity from active context (`get_my_*`, `*_for_me`) and block cross-profile access.
4. Scenario click-to-run includes `actor_patron_id` for run/audit observability.
5. Patron switching in top-bar/profile prompts for switch mode:
   - `fresh`: clear transcript + reset session
   - `keep`: keep transcript + rotate backend session
6. Add ADR-007/008/009 and lightweight model adapter seam for future provider expansion.

## Acceptance Matrix

| Acceptance Criterion | Verification |
|---|---|
| Evaluator can select model variant when launching run | `frontend/src/app/features/run-config-dialog/run-config-dialog.component.ts` + `GET /benchmark/models` |
| Evaluator can compare 2-5 runs in dedicated analytics view | `/#/analytics`, `POST /benchmark/compare`, `frontend/e2e/analytics.spec.ts` |
| Evaluator can see model leaderboard aggregation | `GET /benchmark/leaderboard`, analytics leaderboard table |
| Clicking an Assistant scenario card immediately starts scenario-scoped benchmark execution | `frontend/src/app/features/scenario-sidebar/scenario-sidebar.component.ts`, `POST /benchmark/runs` with `scenario_ids` |
| Assistant chat resets/replays script and forensic ledger shows live trace events | `frontend/src/app/features/chat/chat.component.ts`, `frontend/src/app/features/forensic-ledger/forensic-ledger.component.ts`, `frontend/e2e/assistant-scenario-run.spec.ts` |
| Assistant account flows resolve from active profile without patron-ID prompts | `/chat` `active_patron` contract + active-patron tools + `frontend/e2e/chat-identity.spec.ts` |
| Existing run/report/trace flows keep working with no migration | run-index additive defaults + compatibility tests |
| Docs are updated and internally consistent | `PROJECT_STATUS.md`, `VERSION_LADDER_PROPOSAL.md`, `docs/workstreams/*.md` |
| Required commands pass | commands listed below |

## Test Cases and Scenarios

### Backend
1. `POST /benchmark/runs` persists selected `model_name`.
2. `POST /benchmark/runs` validates/persists `scenario_ids` and `trigger_source`.
3. Scenario-scoped run command forwards repeated `--scenario-id` args to runner.
2. `GET /benchmark/models` returns configured/default model catalog.
3. `POST /benchmark/compare` returns deterministic run/tier/scenario deltas.
4. `GET /benchmark/leaderboard` returns deterministic ordering.
5. Legacy run-index entries without model fields load with defaults.
6. Legacy run-index entries without scenario metadata load with defaults.
7. `/chat` binds `active_patron` and returns `bound_patron_id` + `session_rebound`.
8. Session rotation path isolates state when active patron changes.
9. `actor_patron_id` round-trips through run create/index contracts.

### Frontend
1. Analytics renders for patron and staff personas.
2. Compare deep-link works from `/runs` and `/runs/:runId`.
3. `/#/analytics?runs=...` preloads run selection and comparison.
4. Leaderboard ordering renders rank 1 first.
5. Top-bar quick switch updates active persona and role-scoped nav.
6. Scenario card click launches run, replays script, and updates live audit stream.
7. Forensic ledger deep-link to run detail is visible during live run focus.
8. Patron switch prompt honors `fresh` and `keep` behaviors in chat contexts.
9. Assistant chat requests always carry active patron identity payload.

## Evidence Commands
```bash
uv run pytest agents/tests/integration/test_benchmark_run_lifecycle.py -q
uv run pytest agents/tests/integration/test_chat_identity_binding.py -q
uv run pytest agents/tests/integration/test_run_index_integrity.py -q
uv run pytest agents/tests/integration/test_session_persistence.py -q
uv run pytest agents/tests/unit/test_active_patron_tools.py -q
uv run pytest tests/scenarios/test_contract_compatibility.py -q
cd frontend && npm run build
cd frontend && npm run e2e -- e2e/chat-identity.spec.ts
cd frontend && npm run e2e -- e2e/assistant-scenario-run.spec.ts
cd frontend && npm run e2e -- e2e/analytics.spec.ts
cd frontend && npm run e2e
```

## Assumptions and Defaults
1. `v2.1` model scope is Gemini variants only.
2. Rollout is direct replace with no feature flags.
3. Analytics/comparison is available to all evaluator patrons.
4. Comparison excludes queued/running runs.
5. Legacy runs missing model metadata are treated as `model_name="unknown"`.
6. Assistant scenario card click runs immediately with no extra confirmation modal.
7. Card-triggered execution mode is script replay + benchmark pytest run.
8. Assistant chat resets on every card-triggered run.
9. Staff cross-patron account access in assistant requires explicit active-profile switch.
10. v2.2-prep includes ADR closure and adapter seams only (no full transport/provider migration).
