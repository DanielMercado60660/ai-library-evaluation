## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: System overview reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: infrastructure-services

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# AI Library Evaluation Platform

## Overview

The AI Library project is an **evaluation platform** for testing whether large language models can effectively operate real-world systems. The domain under test is a federated library network — a realistic, complex environment requiring catalog searches, patron management, inter-library loans, and multi-agent coordination.

The key insight: **the entire world is fictional**. The Hanno Memorial Library exists in a world of elephant-themed books, pachyderm nobility, and tusk-derived surnames. This fictional setting creates anti-memorization pressure — models cannot rely on training data and must properly use tools to succeed.

## Research Question

> **Can an LLM run a library?**

More specifically:
- Can it correctly use tools to find information?
- Does it hallucinate when it should say "I don't know"?
- Can it coordinate with other agents without leaking private data?
- How does it handle system failures and edge cases?
- Do different models exhibit different behaviors?

## The Fictional World: Pachyderm Library Network

### Why Fiction?

| Behavior | Real Books (e.g., "Dune") | Fictional Books (e.g., "Tusk and Sensibility") |
|----------|---------------------------|------------------------------------------------|
| Agent "knows" the book | Could be memory OR tool use | **Must be tool use** |
| Agent describes plot | Could be training data | **Must be hallucination if not in catalog** |
| Agent recommends similar titles | Could be real associations | **Must use recommendation tool** |
| Agent invents a sequel | Hard to verify | **Obvious fabrication** |

The elephant-pun world serves as a **canary in the coal mine**. If an agent starts discussing Jane Austen's "Pride and Prejudice" instead of querying for Elaphine Greymarch's "Pride and Pachyderm," we've caught a fundamental failure in tool use.

### The Libraries

**Hanno Memorial Library** (Primary)
- Named after Hanno the Navigator's elephant
- Humanities-focused collection
- Our main evaluation target

**Mastodon Institute of Technology**
- STEM and technical collection
- Research library policies
- Used for A2A testing

**Mammoth Valley Public Library**
- General public collection
- Community-focused
- Used for multi-party A2A scenarios

### The Collection

Books are organized into thirteen strata (genres/categories), numbered 1-13 with Arabic numerals:

| Stratum | Category | Examples |
|---------|----------|----------|
| 1 | Noble Tragedies | "The Fall of Lorde Tuskar," "The Ivory Throne" |
| 2 | Histories & Memoirs | "The Mammoth Wars," "Grey March Histories" |
| 3 | Modern Literary Works | "Tusk and Sensibility," "Pride and Pachyderm" |
| 4 | Technical & Reference | "Principles of Archive Preservation" |
| 5 | Children's Tales & Fables | "The Little Trunk That Could," "Goodnight, Grey Hall" |
| 6 | Poetry & Collected Verse | "Sonnets of the Grey Court" |
| 7 | Philosophy & Treatises | "On the Duty of Remembrance," "The Weight of Memory" |
| 8 | Translated Works | "The Ivory Sutras," "Meditations of the Eastern Keepers" |
| 9 | Extended Tragedies | More noble house drama, expanding stratum 1 |
| 10 | Extended Histories | More institutional histories, expanding stratum 2 |
| 11 | Extended Modern Literary | More contemporary fiction, expanding stratum 3 |
| 12 | Extended Technical | More nonfiction, expanding stratum 4 |
| 13 | Genre Fiction | Mystery, romance, adventure |

### Naming Conventions

**Noble Names** (for authors, characters):
- Tusk-derived: Tuskar, Tuskfall, Tuskmere, Tuskwell
- Ivory-derived: Ivoryn, Ivoreth, Ivornne
- Trunk-derived: Trunvale, Trunkwell, Trunsworth
- Grey-derived: Greyhallow, Greymarch, Greystone
- Pachy-derived: Pachorin, Pachydon, Pachworth
- Mammor-derived: Mammora, Mammorik, Mammontine
- Elaph-derived: Elaphine, Elaphira, Elaphont

**Publishers**:
- Ivory Stacks Press
- Grey Hall Publishing
- Trunk & Tusk Books
- The Mammoth Press

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EVALUATION PLATFORM                                  │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Scenario   │  │    Chaos     │  │    Model     │  │   Metrics    │   │
│  │    Runner    │  │   Controller │  │   Swapper    │  │   Collector  │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       PACHYDERM LIBRARY NETWORK                             │
│                                                                             │
│   ┌─────────────────┐         A2A          ┌─────────────────┐            │
│   │      HANNO      │◄────────────────────►│    MASTODON     │            │
│   │    MEMORIAL     │                      │    INSTITUTE    │            │
│   │                 │                      │                 │            │
│   │  ┌───────────┐  │                      │  ┌───────────┐  │            │
│   │  │   Agent   │  │                      │  │   Agent   │  │            │
│   │  └─────┬─────┘  │                      │  └─────┬─────┘  │            │
│   │        │        │                      │        │        │            │
│   │  ┌─────┴─────┐  │                      │  ┌─────┴─────┐  │            │
│   │  │ Services  │  │                      │  │ Services  │  │            │
│   │  └─────┬─────┘  │                      │  └─────┴─────┘  │            │
│   │        │        │                      │        │        │            │
│   │  ┌─────┴─────┐  │                      │  ┌─────┴─────┐  │            │
│   │  │    DB     │  │                      │  │    DB     │  │            │
│   │  └───────────┘  │                      │  └───────────┘  │            │
│   └─────────────────┘                      └─────────────────┘            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Layers

### Layer 1: Individual Library Stack

Each library is a self-contained deployment with:
- **Agent Layer**: LLM-powered agents (Front Desk, Catalog, Circulation, ILL)
- **Service Layer**: FastAPI microservices (Catalog, Circulation, ILL)
- **Data Layer**: SQLite/PostgreSQL databases

See: [SERVICES.md](./SERVICES.md), [AGENTS.md](./AGENTS.md)

### Layer 2: Network Infrastructure

Shared services enabling cross-library communication:
- **A2A Protocol**: Agent-to-agent messaging (JSON-RPC over HTTP)
- **Union Catalog**: Aggregated holdings across all libraries
- **Registry**: Service discovery and health monitoring

See: [A2A_PROTOCOL.md](./A2A_PROTOCOL.md)

### Layer 3: Evaluation Platform

Infrastructure for testing agent behavior:
- **Scenario Runner**: Execute test cases against agents
- **Chaos Controller**: Inject faults (latency, failures, corrupt data)
- **Model Swapper**: Run same scenarios with different LLMs
- **Metrics Collector**: Decision logging, performance tracking

See: [EVALUATION.md](../archive/archive/2025-architecture/EVALUATION.md)

## Key Design Principles

### 1. Fiction as Evaluation Primitive

The fictional world isn't decoration — it's the core evaluation mechanism. Every elephant pun, every made-up author, every invented ISBN creates a checkpoint where we can verify the agent used tools rather than hallucinated.

### 2. Opacity Preservation (A2A)

Libraries can collaborate without exposing internals. Hanno doesn't need to know how Mastodon implements its catalog — only that it can answer "do you have this book?" This mirrors real distributed systems and enables security testing.

### 3. Data Isolation by Design

Patron data never crosses library boundaries. The A2A protocol enforces this, and evaluation scenarios specifically test for leakage. See: [SECURITY.md](./SECURITY.md)

### 4. Model Agnosticism

The platform abstracts LLM providers behind a common interface. Today we test with Gemini; tomorrow we can swap in GPT-4, Claude, or local models and compare behaviors. See: [MODEL_ABSTRACTION.md](../archive/archive/2025-architecture/MODEL_ABSTRACTION.md)

### 5. Observable Everything

Every agent decision is logged with full context: input, output, tool calls, latency, tokens used. This enables post-hoc analysis, debugging, and automated scoring.

## Evaluation Dimensions

| Dimension | What We Test | Example Scenario |
|-----------|--------------|------------------|
| **Correctness** | Does it return accurate information? | Search for "Tusk and Sensibility" → find correct book |
| **Hallucination** | Does it invent information? | Ask for non-existent "The Ivory Concordance" |
| **Tool Use** | Does it use tools appropriately? | Must call search before answering catalog questions |
| **Resilience** | How does it handle failures? | Catalog service returns 500 error |
| **Security** | Does it leak private data? | A2A request tries to extract patron info |
| **Coordination** | Can it manage multi-step flows? | ILL request spanning multiple libraries |
| **Consistency** | Does it maintain world coherence? | Never mentions real-world books |

## Getting Started

1. **Understand the Domain**: Read this document and [DATA_MODEL.md](./DATA_MODEL.md)
2. **Set Up Services**: Follow the README in the project root
3. **Run Basic Scenarios**: See [EVALUATION.md](../archive/archive/2025-architecture/EVALUATION.md)
4. **Explore A2A**: Set up Mastodon Institute and test cross-library flows
5. **Write New Scenarios**: Extend the evaluation suite

## File Structure

```
ai-library/
├── docs/architecture/      # You are here
├── core/                   # Model abstraction, observability
├── eval/                   # Evaluation framework
├── network/                # A2A infrastructure
├── libraries/              # Per-library configurations
│   ├── hanno/              # Hanno Memorial data & config
│   └── mastodon/           # Mastodon Institute data & config
├── services/               # Microservices
│   ├── catalog/
│   ├── circulation/
│   └── ill/
├── agents/                 # LLM-powered agents
└── shared/                 # Common schemas, constants
```

## Related Documents

- [SERVICES.md](./SERVICES.md) — Microservice API specifications
- [AGENTS.md](./AGENTS.md) — Agent architecture and tools
- [A2A_PROTOCOL.md](./A2A_PROTOCOL.md) — Inter-library communication
- [DATA_MODEL.md](./DATA_MODEL.md) — Entity relationships and schemas
- [SECURITY.md](./SECURITY.md) — Data isolation and privacy rules
- [EVALUATION.md](../archive/archive/2025-architecture/EVALUATION.md) — Testing framework and scenarios
- [MODEL_ABSTRACTION.md](../archive/archive/2025-architecture/MODEL_ABSTRACTION.md) — LLM provider interface
