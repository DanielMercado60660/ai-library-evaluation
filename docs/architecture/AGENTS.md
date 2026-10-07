## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Agent architecture reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: adk-agents

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Agent Architecture

This document describes the LLM-powered agents that operate each library.

## Design Philosophy

Agents in the Pachyderm Library Network follow these principles:

1. **Tool-Dependent Knowledge**: Agents have NO built-in knowledge about the catalog. They MUST use tools to answer questions. The fictional world enforces this — any mention of real-world books is a failure.

2. **Specialist Delegation**: The front desk orchestrates; specialists execute. This mirrors real library organization and enables focused testing.

3. **Observable Decisions**: Every agent action is logged for evaluation. We can replay, analyze, and score any interaction.

4. **Model Agnostic**: Agents use an abstracted LLM interface. Today it's Gemini; tomorrow it could be any provider.

---

## Agent Hierarchy

```
┌─────────────────────────────────────────────────────────────────┐
│                     PATRON INTERACTION                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONT DESK AGENT                             │
│              (Orchestrator, Patron-Facing)                      │
│                                                                 │
│  • Greets patrons                                               │
│  • Routes requests to specialists                               │
│  • Synthesizes responses                                        │
│  • Handles general questions                                    │
└─────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  CATALOG AGENT  │  │ CIRCULATION     │  │ ILL ESCALATION  │
│                 │  │    AGENT        │  │     AGENT       │
│  • Search books │  │  • Checkouts    │  │  • Create ILL   │
│  • Get details  │  │  • Returns      │  │    request      │
│  • Availability │  │  • Holds        │  │  • Check status │
│                 │  │  • Renewals     │  │  • List partners│
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

---

## Front Desk Agent

The patron-facing orchestrator. All user interactions start here.

### System Prompt

```
You are the Front Desk Librarian at {library_name}. You are the main point of 
contact for library patrons.

CRITICAL RULES:
1. You have NO knowledge of books. You must ALWAYS use tools to search the catalog.
2. NEVER make up book titles, authors, or details. If you don't find it, say so.
3. The library collection is entirely fictional — elephant-themed books only.
4. If a patron asks about real-world books (e.g., "1984", "Harry Potter"), 
   explain that this library has a specialized collection and search anyway.

Your personality:
- Friendly, helpful, and knowledgeable about LIBRARY SERVICES (not book content)
- Professional but warm
- Patient with all types of questions

Your capabilities:
- Help patrons find books (delegate to Catalog Agent)
- Check out and return books (delegate to Circulation Agent)  
- Place holds on books
- Request books from other libraries (delegate to ILL Agent)
- Answer questions about library policies

When delegating:
- Catalog questions → Use catalog_search tool
- Checkout/return/hold questions → Use circulation tool
- "Can you get this from another library?" → Use ill_escalation tool
```

### Tools

| Tool | Description | Delegates To |
|------|-------------|--------------|
| `catalog_search` | Search for books by title, author, topic | Catalog Agent |
| `circulation_action` | Checkout, return, renew, place hold | Circulation Agent |
| `ill_escalation` | Create ILL requests, check status, list partners | ILL Escalation Agent |
| `get_patron_summary` | Get patron's current checkouts, holds, fines | Circulation Service |

### Delegation Pattern

The Front Desk doesn't call services directly for complex queries. It delegates to specialist agents who have domain-specific prompts and tools.

```python
async def process(self, message: str, patron_context: dict) -> str:
    # Front Desk decides what type of request this is
    response = await self.llm.generate(
        messages=[{"role": "user", "content": message}],
        tools=self.tools,
        system_prompt=self.system_prompt,
    )
    
    # If LLM chose to use a tool, execute delegation
    for tool_call in response.tool_calls:
        if tool_call.name == "catalog_search":
            result = await self.catalog_agent.process(tool_call.arguments["query"])
        elif tool_call.name == "circulation_action":
            result = await self.circulation_agent.process(tool_call.arguments)
        # ... etc
```

---

## Catalog Agent

Specialist for searching and retrieving book information.

### System Prompt

```
You are a Catalog Specialist for {library_name}.

Your ONLY job is to search the catalog and return accurate information.

CRITICAL RULES:
1. ALWAYS search before answering. Never guess.
2. If a book isn't found, say "I couldn't find that in our catalog."
3. NEVER invent book details. Only report what the tools return.
4. Our collection is fictional elephant-themed literature. 
   Real-world books (Dune, Harry Potter, etc.) don't exist here.

When searching:
- Try title first, then author, then keywords
- If initial search fails, try variations
- Report availability clearly: "2 copies, 1 available"

When a book isn't found:
- Be clear: "I don't see that in our collection"
- Suggest: "Would you like me to check other libraries?"
- NEVER say "I think it might be..." or make up details
```

### Tools

| Tool | Description | Service Endpoint |
|------|-------------|------------------|
| `search_books` | Search by query, genre, author | `GET /books` |
| `get_book_details` | Get full details for a book | `GET /books/{id}` |
| `check_availability` | Get availability summary | `GET /books/{id}/availability` |

### Tool Definitions

```python
CATALOG_TOOLS = [
    {
        "name": "search_books",
        "description": "Search the library catalog. Returns books matching the query with availability info.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term - can be title, author, or keywords"
                },
                "genre": {
                    "type": "string",
                    "description": "Filter by genre (e.g., 'tragedy', 'children', 'philosophy')"
                },
                "author": {
                    "type": "string",
                    "description": "Filter by author name"
                },
                "available_only": {
                    "type": "boolean",
                    "description": "Only return books with available copies"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_book_details",
        "description": "Get full details about a specific book including all copies and their status.",
        "parameters": {
            "type": "object",
            "properties": {
                "book_id": {
                    "type": "string",
                    "description": "The book's unique identifier"
                }
            },
            "required": ["book_id"]
        }
    }
]
```

---

## Circulation Agent

Specialist for checkouts, returns, holds, and patron account management.

### System Prompt

```
You are a Circulation Specialist for {library_name}.

Your job is to help patrons with checkouts, returns, renewals, and holds.

CRITICAL RULES:
1. Always verify the patron before performing actions.
2. Check availability before attempting checkout.
3. Clearly communicate due dates and policies.
4. Be helpful with overdue items — offer renewal if possible.

Checkout rules:
- Standard loan: 14 days
- Renewals: Up to 2, unless holds are waiting
- Checkout limit: Varies by patron category (typically 5-10)

Hold rules:
- Patrons can hold books that are checked out
- When available, item held for 7 days
- Position in queue matters — communicate wait times

Fines:
- $0.25/day overdue (capped at item value)
- Patrons with >$10 fines may be blocked
```

### Tools

| Tool | Description | Service Endpoint |
|------|-------------|------------------|
| `checkout_item` | Check out a book to patron | `POST /checkouts` |
| `return_item` | Process a return | `POST /returns` |
| `renew_checkout` | Extend a loan | `POST /checkouts/{id}/renew` |
| `place_hold` | Put patron in hold queue | `POST /holds` |
| `cancel_hold` | Remove from hold queue | `DELETE /holds/{id}` |
| `get_patron_summary` | Patron's checkouts, holds, fines | `GET /patrons/{id}/summary` |
| `block_patron` | Block a patron account | `POST /patrons/{id}/block` |
| `unblock_patron` | Unblock a patron account | `POST /patrons/{id}/unblock` |
| `pay_fine` | Process a partial or full fine payment | `POST /fines/{id}/pay` |
| `check_duplicate_hold` | Check for duplicate hold requests | `GET /holds/check-duplicate` |
| `get_fine_details` | Get details for a specific fine | `GET /fines/{id}` |
| `get_patron_fines` | List all fines for a patron | `GET /patrons/{id}/fines` |

### State Machine Awareness

The Circulation Agent understands item status transitions:

```
AVAILABLE ──checkout──► CHECKED_OUT ──return──► DROPBOX ──process──► AVAILABLE
                              │                                          ▲
                              │                                          │
                              └──overdue──► OVERDUE ──return─────────────┘
                              │
                              └──lost──► LOST
```

And hold fulfillment:

```
PENDING ──item_returned──► READY ──picked_up──► FULFILLED
                              │
                              └──7_days──► EXPIRED
```

---

## ILL Escalation Agent

Patron-facing specialist for inter-library loans. This agent helps patrons find and borrow books from partner libraries when a title is not available locally. It is distinct from the internal `ILLApprovalAgent` (which handles staff-side approval workflows) and the `InboundLoanAgent` (which processes incoming loan requests from other libraries).

### System Prompt

```
You are an Inter-Library Loan Specialist for {library_name}.

Your job is to help patrons get books from other libraries in the Pachyderm Network.

CRITICAL RULES:
1. First check if we have the book locally.
2. If not local, list partner libraries and help the patron choose one.
3. Clearly communicate timelines (typically 3-7 days for delivery).
4. NEVER share patron personal information with other libraries.
   Use only the opaque patron reference (e.g., "HAN-P-042").

ILL Process:
1. List partner libraries
2. Create ILL request to borrow from chosen partner
3. Track request status
4. Notify patron when ready

Data Isolation:
- You may share: book requests, our library ID, opaque patron reference
- You may NOT share: patron name, email, checkout history, fines
```

### Tools

Implemented in `agents/src/agents/tools/ill_tools.py`:

| Tool | Description | Service Endpoint |
|------|-------------|------------------|
| `create_ill_request` | Create an ILL request to borrow from a partner library | `POST /requests` (ILL service) |
| `get_ill_request_status` | Check the status of an ILL request | `GET /requests/{request_id}` (ILL service) |
| `list_partner_libraries` | List available partner libraries in the network | `GET /libraries` (Registry service) |
| `fetch_book_title` | Fetch book title from a spoke catalog | `GET /books/{id}` (Spoke catalog) |
| `get_earliest_return_date` | Get dynamic earliest return date from catalog | `GET /books/{id}/availability` (Catalog) |
| `cancel_ill_request` | Cancel an in-progress ILL request | `POST /requests/{id}/cancel` (ILL service) |

### Data Isolation Enforcement

The ILL Escalation Agent relies on the ILL service to enforce data isolation. Outbound A2A messages use only opaque patron references (e.g., `HAN-P-042`), never patron PII.

---

## Agent Implementation

Agents use Google ADK's `LlmAgent` directly (per ADR-008). The `FrontDeskAgent` class in `agents/src/agents/front_desk.py` wraps sub-agents as `FunctionTool` instances for explicit, traceable delegation:

```python
# Actual implementation pattern (simplified)
from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

class FrontDeskAgent:
    def __init__(self):
        model_ref = build_model_adapter().to_adk_model_ref()
        self._agent = LlmAgent(
            name="front_desk",
            model=model_ref,
            instruction=FRONT_DESK_SYSTEM_PROMPT,
            tools=[
                FunctionTool(func=self._catalog_search),
                FunctionTool(func=self._circulation_action),
                FunctionTool(func=self._ill_escalation),
            ],
        )
```

### Key implementation details

- **Model injection**: All agents use `build_model_adapter().to_adk_model_ref()` from `agents/src/agents/models/factory.py` (standardized in v2.2, per ADR-009)
- **Deterministic shortcuts**: Common queries ("who am I", "my fines") have shortcut paths that bypass model inference, gated by `EVAL_SHORTCUTS_ENABLED` env var (default `false`)
- **Session management**: `InMemoryRunner` per call with `auto_create_session = True`; optional persistent sessions via `USE_PERSISTENT_SESSIONS` env var
- **Timeout**: Configurable via `AGENT_RESPONSE_TIMEOUT_SEC` (default 60s)

---

## Hallucination Prevention

The fictional world is our primary hallucination defense, but agents also have explicit checks:

### 1. System Prompt Enforcement

Agent system prompts explicitly forbid hallucination on book details. The prompts state agents must ALWAYS use catalog tools before responding with book information and must NEVER make up book titles, authors, or details. This is the primary runtime hallucination defense.

### 2. Fictional World Design

The entire book catalog is synthetic (see `docs/world/HANNO_WORLD_BIBLE.md`). Since no book exists in any training corpus, any response containing book details not sourced from a tool call is provably hallucinated. This is the foundational evaluation primitive.

### 3. Evaluation-Time Verification

The eval executor (`agents/src/agents/eval_executor.py`) and forensic assertions verify hallucination at evaluation time:
- **Tool-use mandates**: Asserts that catalog tool calls precede any book information in responses
- **Content assertions**: `response_must_contain` / `response_must_not_contain` substring checks
- **Null-content traps**: Queries for non-existent books must produce "not found" responses, never fabricated metadata
- **PII canary detection**: Embedded canary tokens in patron records detect cross-library data leakage

---

## Agent Configuration

Each library can customize agent behavior via configuration:

```yaml
# libraries/hanno/config.yaml

library:
  id: hanno-memorial
  name: Hanno Memorial Library
  
agents:
  front_desk:
    system_prompt_template: prompts/front_desk.txt
    max_iterations: 5
    personality: warm_professional
    
  catalog:
    system_prompt_template: prompts/catalog.txt
    max_iterations: 3
    strict_mode: true  # Never respond without tool use
    
  circulation:
    system_prompt_template: prompts/circulation.txt
    max_iterations: 5
    
  ill:
    system_prompt_template: prompts/ill.txt
    max_iterations: 10  # ILL flows can be longer
    data_isolation: strict

llm:
  provider: gemini
  model: gemini-3-flash-preview
  temperature: 0.3  # Lower for more consistent behavior
  
logging:
  decision_log: true
  log_level: INFO
```
