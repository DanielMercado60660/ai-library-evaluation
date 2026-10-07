# Fully Finished Target State — Acceptance Checklist

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Internal acceptance gates derived from ProjectGoal.md research vision
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Previous aspirational target-state blueprint
- Related Workstream: all

## Purpose

This document translates the research vision described in [`ProjectGoal.md`](../../ProjectGoal.md) into concrete, verifiable acceptance gates. ProjectGoal.md is the public-facing pitch; this document is the internal checklist for tracking what's done, what's partial, and what remains.

---

## 1. Fiction as Evaluation Primitive

**Vision (ProjectGoal.md)**: 635+ synthetic books across eight literary strata, entirely fictional, forcing tool use and making hallucination unambiguous.

| Gate | Status | Evidence |
|------|--------|----------|
| Synthetic book catalog generated | Done | 635 books across 13 strata in `data/` (10 batch files + seed catalog) |
| Zero real-world book titles | Done | Quality checks in world bible; no real titles in catalog |
| Sparse summaries (hallucination magnets) | Done | All summaries deliberately minimal |
| World bible canonical and unified | Done | `docs/world/HANNO_WORLD_BIBLE.md` (v2.0.0, unified 2026-02-10) |
| Null-content trap suite | Done | 10 null-content trap scenarios in test suite |
| PII canary detection suite | Done | 8 canary attack scenarios |

---

## 2. Architecture as Research Design

**Vision (ProjectGoal.md)**: Each library is a genuinely independent microservice with its own database, agent stack, and API surface.

| Gate | Status | Evidence |
|------|--------|----------|
| Independent microservices (catalog/circulation/ILL/registry) | Done | 4 services on ports 8001-8004 with isolated SQLite DBs |
| ADK multi-agent delegation | Done | FrontDeskAgent → CatalogAgent, CirculationAgent, ILLEscalationAgent |
| MCP tool integration | Done | FastMCP servers in each service; 6 circulation + 3 ILL mutation tools |
| A2A cross-library protocol | Done | Registry-hosted relay (send/poll/ack), data isolation enforced |
| Spoke catalog federation | Done | 4 spoke instances (mastodon, mammoth, ivory, tusk) on ports 8011-8014 |
| Docker Compose orchestration | Done | All services + frontend in `docker-compose.yml` |
| Frontend operator console | Done | Angular 18, 3-panel layout, chat + forensic ledger + scenario sidebar |

---

## 3. Deterministic Evaluation (Phase 1)

**Vision (ProjectGoal.md)**: Automated scenario suites with forensic SQL assertions. No LLM-as-judge. Binary pass/fail.

| Gate | Status | Evidence |
|------|--------|----------|
| Tiered scenario catalog (Tier 1-3) | Done | 26 scenarios in `tests/scenarios/scenario_manifest.json` |
| Inventory conservation assertion | Done | `inventory_conservation_v1` in forensic assertions |
| Financial integrity assertion | Done | `financial_integrity_v1` in forensic assertions |
| Tool-use mandate verification | Done | Eval executor asserts tool calls in JSONL traces |
| Privacy boundary enforcement | Done | A2A payload validation, PII canary scanner |
| Null-content trap enforcement | Done | 10 scenarios with binary hallucination verdict |
| Scripted eval executor | Done | `agents/src/agents/eval_executor.py` — replays via POST /chat |
| Eval report generation | Done | v1.5 schema with `eval_details` |
| In-process test execution (no API key needed) | Done | `uv run pytest -q` runs 649 tests deterministically |
| Tier 4 adversarial scenarios | Planned | Turns-till-failure, adversarial LLM probing |

---

## 4. Adversarial Benchmark (Phase 2)

**Vision (ProjectGoal.md)**: Turns-till-failure, chaos injection, sandbox mode.

| Gate | Status | Evidence |
|------|--------|----------|
| Chaos injection framework | Done | Deterministic fault profiles with sequenced faults |
| Service timeout/outage injection | Done | 4 built-in fault profiles |
| Resilience scoring | Done | Weighted composites (recovery time, degradation, error quality) |
| Open-ended benchmark generation | Done | PatronRequestGenerator, template-based, seeded RNG |
| Benchmark session execution | Done | BenchmarkSessionExecutor with time budget |
| Turns-till-failure red-teaming | Planned | Automated adversarial query escalation |
| Sandbox mode (live MCP inspection) | Partial | Chat interface with trace overlay exists; full protocol inspector planned |

---

## 5. Cross-Model Comparison

**Vision (ProjectGoal.md)**: Running the same scenario suite against different LLMs with training-data-contamination-controlled comparison.

| Gate | Status | Evidence |
|------|--------|----------|
| Model-aware run metadata | Done | `model_name`, `model_family` in run contracts |
| Comparison API | Done | `POST /benchmark/compare`, `GET /benchmark/leaderboard` |
| Model leaderboard | Done | `/benchmark/leaderboard` endpoint + frontend analytics |
| Run-to-run delta comparison | Done | Compare workbench in `/#/analytics` route |
| Multi-provider model adapter | Partial | Gemini adapter implemented; contract exists for expansion |
| Normalized cross-model scoring | Partial | Same scenarios run across models; normalization logic present |

---

## 6. Operator Platform

**Vision (ProjectGoal.md)**: Angular frontend with chat, MCP inspector, forensic ledger, trace replay, scenario heatmaps, topology visualization.

| Gate | Status | Evidence |
|------|--------|----------|
| 3-panel layout (sidebar, chat, ledger) | Done | Angular 18 standalone components |
| Run configuration dialog | Done | Eval/Pytest/Benchmark radio with full config |
| Live trace view | Done | ForensicLedger with eval step cards, benchmark cards |
| PDF report export | Done | jspdf + jspdf-autotable, "Print Report" button |
| System status dashboard | Done | SystemStatusService polls `/health` on all 5 services |
| Scenario heatmap visualization | Planned | |
| Network topology visualization | Planned | |
| Full MCP protocol inspector | Planned | |
| Session replay | Partial | Trace events logged; visual replay not yet built |

---

## 7. RL Data Generation

**Vision (ProjectGoal.md)**: Trajectory export, deterministic rewards, preference pairs.

| Gate | Status | Evidence |
|------|--------|----------|
| JSONL trace emission | Done | TraceWriter emits structured events |
| Step trajectory format | Planned | Versioned `(state, action, reward)` export |
| Preference-pair generation | Planned | Positive/negative pair builder |
| RL export contract | Planned | Stable, versioned format for downstream pipelines |

---

## 8. Open-Source Foundation

**Vision (ProjectGoal.md)**: Local stack, core scenarios, synthetic data pipeline, forensic judge.

| Gate | Status | Evidence |
|------|--------|----------|
| One-command local setup | Done | `docker compose up --build -d` |
| Core benchmark scenarios included | Done | 26 scenarios in test suite |
| CI pipeline | Done | GitHub Actions with parallel frontend/backend jobs |
| API key placeholder (no secrets in repo) | Done | `.env.example` with placeholder |
| Quick start documentation | Done | `docs/development/QUICK_START.md` |
| Domain-transfer toolkit | Planned | World-bible-to-corpus generation for new domains |
| Community extension model | Planned | Scenario pack plugin contract |

---

## Summary

| Category | Done | Partial | Planned | Total |
|----------|------|---------|---------|-------|
| Fiction as Evaluation Primitive | 6 | 0 | 0 | 6 |
| Architecture as Research Design | 7 | 0 | 0 | 7 |
| Deterministic Evaluation | 9 | 0 | 1 | 10 |
| Adversarial Benchmark | 5 | 1 | 1 | 7 |
| Cross-Model Comparison | 4 | 2 | 0 | 6 |
| Operator Platform | 5 | 1 | 3 | 9 |
| RL Data Generation | 1 | 0 | 3 | 4 |
| Open-Source Foundation | 5 | 0 | 2 | 7 |
| **Total** | **42** | **4** | **10** | **56** |

**75% of acceptance gates are complete. The platform is operational as a locally-hosted alpha with the core evaluation methodology fully functional.**

---

## Out of Scope Even at Fully Finished
- Full enterprise SaaS operations (multi-tenant IAM, billing, hard SLO contracts)
- Real-world public library policy parity
- Elimination of all human qualitative review for subjective interaction quality

## Tracking References
- Research vision: [`ProjectGoal.md`](../../ProjectGoal.md)
- Version roadmap: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Live status: `docs/status/PROJECT_STATUS.md`
