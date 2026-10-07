# Can an AI Run a Library?

## An Evaluation Platform for Autonomous Agent Competence

---

Most LLM benchmarks test reasoning or code generation — tasks with clear inputs and outputs. But real-world autonomous systems don't just answer questions. They manage state, enforce policies, coordinate across organizational boundaries, and maintain data integrity over extended interactions. How do you evaluate *that*?

We built a federated library network to find out.

---

## The Core Insight: Fiction as Evaluation Primitive

The Pachyderm Library Network is entirely fictional — five libraries serving a world of elephant-themed literature, pachyderm nobility, and tusk-derived surnames. This isn't decorative. It's the foundation of the evaluation methodology.

Familiar titles make it hard to distinguish catalog lookup from training-data recall. A controlled fictional catalog supplies ground truth that can be checked against actual tool traces and database state. Fiction reduces familiar-content shortcuts; it does not guarantee that published synthetic data will never appear in a future training corpus. Unsupported plot summaries and metadata can be checked against the supplied collection.

A network manifest covering **635 synthetic books** span thirteen literary strata (Noble Tragedies, Histories & Memoirs, Poetry, Philosophy, Children's Tales, and more), each with complete metadata, ISBNs, holdings, and cross-library availability. The entire world — authors, publishers, patrons, transaction histories — is generated to be *plausible but controlled*.

---

## Architecture as Research Design

The configured network has a hub catalog and four spoke catalogs with separate databases and API surfaces. The current agent API and run control plane are centralized. The long-term design calls for more independent library agents; the existing topology already supports testing cross-service coordination:

| Layer | Technology | What It Enables |
|---|---|---|
| **Agents** | Google ADK | Multi-agent delegation — a front desk agent routes to catalog, circulation, and ILL specialists. Tests whether the LLM can orchestrate complex workflows through sub-agent coordination. |
| **Tools** | Model Context Protocol (MCP) | Structured tool access — catalog search, checkout, holds, fine calculation, patron lookup. Every tool call is traced, creating a complete audit log for deterministic verification. |
| **Federation** | Agent-to-Agent Protocol (A2A) | Cross-library communication for inter-library loans. Libraries cooperate *without exposing internals* — Hanno Memorial doesn't see Mammoth Valley's patron records. Tests opacity preservation and information boundary enforcement. |
| **Services** | FastAPI + SQLite | Per-library microservices with isolated databases. Enables real failure injection — what happens when a spoke library goes offline mid-ILL-request? |

Service boundaries, A2A payload validation, MCP traces, and SQL assertions provide evidence for checking coordination and policy behavior. Coverage remains bounded by the scenarios and assertions implemented.

---

## Evaluation: Two Phases, Different Questions

### Phase 1 — Deterministic Evaluation

*Does the agent do exactly what it should?*

Automated scenario suites run through tiered test cases — from simple catalog lookups (Tier 1) through multi-step circulation workflows (Tier 2) to cross-library ILL negotiations with chaos injection (Tier 3). After each scenario, **forensic SQL assertions** verify formal invariants against the actual database state:

- **Inventory conservation** — book instance counts balance exactly across checkouts, returns, holds, and ILL transfers. No phantom copies created, none lost.
- **Financial integrity** — fine totals match the formula ($0.25/day × overdue days). No invented charges, no missing fees.
- **Hold queue ordering** — FIFO ordering maintained with no queue jumps, even under concurrent requests.
- **Tool-use mandates** — the agent never generates book details without a preceding catalog tool call. Every assertion is traced back to its source.
- **Privacy boundary enforcement** — patron data never crosses library boundaries in A2A responses. PII canary tokens embedded in patron records detect any leakage.
- **Null-content traps** — queries for books that don't exist must produce "not found" responses, never fabricated metadata.

The deterministic harness uses SQL queries, trace checks, and rule-based scoring rather than an LLM judge. The current regression suite includes service, scenario, and agent tests; it is not a count of independent model evaluations. The `--include-adk` path uses a deterministic topology adapter with synthetic traces, not live Gemini inference.

### Phase 2 — Adversarial Benchmark

*How does the agent fail, and when?*

**Turns-till-failure (research direction)**: A proposed extension uses smaller LLMs to generate adversarial queries — probing context windows, testing tool-chain coherence over extended multi-turn conversations, and escalating request complexity until the agent produces an invariant violation.

**Chaos injection**: Controlled fault profiles with deterministic fault sequencing — service timeouts, HTTP 500 errors, malformed A2A responses, intermittent spoke outages. Each profile is reproducible (faults trigger on specific call indices, not random probability). Resilience scoring uses weighted composites across recovery time, degradation quality, and user-facing error quality.

**Sandbox mode**: Open-ended chat interface with live MCP protocol inspection, forensic ledger overlay, trace replay, and network topology visualization. Supports patron switching for identity-boundary testing and scenario-triggered evaluation runs from the UI.

---

## What This Tests That Other Benchmarks Don't

| Capability | How We Test It |
|---|---|
| **Stateful tool orchestration** | Multi-step workflows (search → availability check → hold → ILL request → confirmation) with database-verified outcomes |
| **Multi-agent delegation** | Front desk agent must route to the right specialist; incorrect delegation is a traceable failure |
| **Cross-organizational coordination** | ILL workflows span independent agent systems with separate databases — not shared-context multi-agent chat |
| **Information boundary enforcement** | A2A protocol tests whether the agent leaks patron data across library trust boundaries |
| **Hallucination under anti-memorization pressure** | Controlled fictional data makes unsupported catalog claims measurable against tools and ground truth |
| **Resilience under infrastructure failure** | Chaos injection with deterministic fault profiles; scored on recovery, not just survival |
| **Financial and inventory integrity** | SQL invariant assertions that would catch real-world data corruption in production systems |

---

## Current State

The platform is a local research alpha. The latest validation and limitations are recorded in [publication readiness](docs/status/PUBLICATION_READINESS.md). Implemented areas include:

- 5 configured catalog instances with separate databases and centralized agent orchestration
- 13+ scripted evaluation scenarios across 3 difficulty tiers
- Forensic trace contract with JSONL audit logs and SQL assertion framework
- Chaos testing framework with 4 built-in fault profiles and resilience scoring
- Safety packs: null-content traps (10 cases) and PII canary detection (8 attack scenarios)
- Run control plane with async orchestration, model comparison, and leaderboard APIs
- Angular frontend with chat interface, MCP protocol inspector, forensic ledger, trace replay, scenario heatmaps, and network topology visualization

**Stack**: Python · FastAPI · SQLite · Google ADK · MCP · A2A · Angular 18 · pytest

---

## Research Direction

The immediate question is model comparison — running the same scenario suite against different LLMs and comparing where each fails. The controlled fictional domain reduces familiar-content recall and supports reproducible comparisons, while live-model conclusions still require observed runs with matched configurations.

The broader question is whether deterministic, invariant-based evaluation — borrowed from database testing and formal verification rather than NLP evaluation traditions — is a more reliable signal of autonomous agent readiness than the accuracy/F1/human-preference metrics that dominate current benchmarks.

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/DanielMercado60660/ai-library-evaluation.git
cd ai-library-evaluation
uv sync --frozen --all-packages

# Run the full deterministic test suite
uv run pytest -q

# Start the stack (Docker)
cp .env.example .env
# Set your live model credentials in .env.
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d

# Open the operator UI
open http://localhost:4200
```

See [`docs/development/QUICK_START.md`](docs/development/QUICK_START.md) for detailed setup.

---

## Documentation

- [`ProjectGoal.md`](ProjectGoal.md) — This document: the research vision
- [`docs/development/QUICK_START.md`](docs/development/QUICK_START.md) — Getting started guide
- [`docs/architecture/`](docs/architecture/) — System design (A2A protocol, data model, security)
- [`docs/world/`](docs/world/) — The fictional universe (synthetic data generation, lore)
- [`docs/archive/`](docs/archive/) — Historical documentation

---

*Fictional books. Real state. Inspectable evidence.*
