# Architecture Recommendations

## Doc Header
- Doc Status: Draft
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Post-v2.0 architectural improvements for MCP, ADK, A2A, and microservices
- Source of Truth: This file
- Related Workstream: adk-agents, a2a-network, mcp-tooling, infrastructure-services

---

## Executive Summary

This document provides actionable recommendations for evolving the AI Library evaluation platform's architecture. The platform currently implements a sophisticated multi-agent system with ADK agents, MCP tooling, A2A networking, and microservices. While the v2.0 foundation is solid, several opportunities exist to improve consistency, reduce technical debt, and prepare for cross-model benchmarking (v2.1).

### Current Assessment

| Component | Status | Grade | Primary Gap |
|-----------|--------|-------|-------------|
| MCP Servers | Implemented | B+ | Not integrated with FastAPI lifecycle |
| ADK Agents | Implemented | B+ | Mixed delegation patterns |
| A2A Runtime | Implemented | A- | In-memory only (no persistence) |
| Microservices | Implemented | A | Good separation, auth, observability |
| Tool Layer | Implemented | B | HTTP vs MCP duplication |

---

## 1. MCP (Model Context Protocol) Recommendations

> **v2.2 Update:** 6 circulation mutation tools (`checkout_item`, `return_item`, `place_hold`, `cancel_hold`, `pay_fine`, `renew_checkout`) and 3 ILL mutation tools (`create_ill_request`, `approve_ill_request`, `deny_ill_request`) have been added to the respective MCP servers. These tools are fully functional and tested.

### 1.1 Clarify MCP vs HTTP Tool Strategy

**Current State:**
- MCP servers exist in each service (`services/*/mcp_server.py`)
- Agents use HTTP tools (`agents/tools/*.py`) instead of MCP tools
- `MCPConnectionManager` exists but is not the primary path

**Recommendation: Choose ONE Primary Pattern**

#### Option A: MCP-First (Recommended for v2.1+)
Make MCP the primary interface for agent-service communication.

**Benefits:**
- Native ADK integration with `McpToolset`
- Standardized tool discovery
- Better type safety through Pydantic schemas
- Aligns with Google's ADK vision

**Implementation:**
```python
# agents/tools/catalog_tools.py - Refactored
from agents.mcp.connection_manager import MCPConnectionManager

async def search_books(query: str, ...) -> dict:
    async with MCPConnectionManager().toolset_context("catalog") as toolset:
        result = await toolset.search_books(query=query, ...)
        return json.loads(result)  # MCP returns JSON strings
```

**Tasks:**
1. Refactor `agents/tools/*.py` to use `MCPConnectionManager`
2. Add SSE transport to MCP servers for HTTP-based access
3. Deprecate direct HTTP tool calls
4. Update tests to mock MCP instead of HTTP

#### Option B: HTTP-First (Current Implicit Pattern)
Document that MCP is for external consumers only; internal agents use HTTP.

**Benefits:**
- Simpler debugging (direct HTTP calls)
- No subprocess management
- Works with existing test infrastructure

**Tasks:**
1. Document HTTP-as-primary pattern
2. Remove unused `MCPConnectionManager` or move to `contrib/`
3. Keep MCP servers for external tool consumers

### 1.2 Add SSE Transport Support

**Current:** MCP servers only support stdio transport.

**Recommendation:** Add SSE (Server-Sent Events) transport for easier integration.

```python
# services/catalog/src/catalog/mcp_server.py
@mcp.server.sse
async def handle_sse(request):
    """SSE endpoint for MCP over HTTP."""
    ...

# In FastAPI routes
from mcp.server.sse import SseServerTransport

@sse_transport.handle_post_message
async def mcp_endpoint(request: Request):
    ...
```

**ADR Needed:** ADR-007-mcp-transport-strategy.md

### 1.3 Consolidate Tool Definitions

**Current:** Tool schemas defined twice (MCP decorators + `*_TOOLS` JSON).

**Recommendation:** Generate `*_TOOLS` JSON from MCP server introspection.

```python
# scripts/generate_tool_schemas.py
async def export_mcp_tools():
    tools = await mcp.list_tools()
    with open("agents/tools/generated_catalog_tools.json", "w") as f:
        json.dump(tools, f, indent=2)
```

---

## 2. ADK (Agent Development Kit) Recommendations

### 2.1 Standardize Agent Delegation Pattern

**Status: Implemented in v2.2.** ADR-008 accepted. The compatibility-first delegation standard is in place: `FrontDeskAgent` class wrapper is the stable runtime entrypoint with explicit delegation to specialist agents (catalog, circulation, ILL). Factory constructors remain as migration seams for future full sub-agent composition (v3.0 target).

**Current State:** Two competing patterns:

```python
# Pattern A: Class-based wrapper with direct tools (FrontDeskAgent)
class FrontDeskAgent:
    def __init__(self):
        self._agent = LlmAgent(tools=[...])  # Direct tools

# Pattern B: Factory function with sub-agents (create_front_desk_agent)
def create_front_desk_agent():
    return LlmAgent(sub_agents=[...])  # Sub-agent delegation
```

**Recommendation: Standardize on Sub-Agent Pattern**

Sub-agents provide:
- Better separation of concerns
- Cleaner system prompt boundaries
- Natural delegation semantics
- Easier to test in isolation

**Refactoring Plan:**

```python
# agents/front_desk.py - Standardized
from google.adk.agents import LlmAgent
from agents.catalog_agent import create_catalog_agent
from agents.circulation_agent import create_circulation_agent
from agents.ill_escalation_agent import create_ill_escalation_agent

def create_front_desk_agent() -> LlmAgent:
    """Create front desk agent with specialist sub-agents."""
    return LlmAgent(
        model=MODEL_NAME,
        name="front_desk_agent",
        instruction=FRONT_DESK_SYSTEM_PROMPT,
        sub_agents=[
            create_catalog_agent(),
            create_circulation_agent(),
            create_ill_escalation_agent(),
        ],
        output_key="front_desk_response",
    )

# Remove FrontDeskAgent class (breaking change for v3.0)
# Provide adapter for backward compatibility in v2.x
```

**ADR Needed:** ADR-008-agent-delegation-pattern.md -- **Created and accepted.**

Additionally, the `EVAL_SHORTCUTS_ENABLED` env var (default `false`) now gates all deterministic shortcut/fallback paths in agents, ensuring evaluation scenarios exercise the full LLM reasoning path.

### 2.2 Implement Model Adapter Interface (v2.1)

**Status: Implemented in v2.2.** ADR-009 accepted. All agents now use `build_model_adapter().to_adk_model_ref()` for standardized model injection via `agents/src/agents/models/factory.py`, `base.py`, and `gemini_adapter.py`. Gemini is the only shipped adapter; new providers implement the same contract.

**Current:** Hardcoded to Gemini (ADR-005).

**Recommendation:** Abstract model provider for v2.1 cross-model comparison.

```python
# agents/models/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class ModelAdapter(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        ...
    
    @abstractmethod
    async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
        ...

# agents/models/gemini_adapter.py
class GeminiAdapter(ModelAdapter):
    def __init__(self, model_name: str):
        self._model = model_name
    
    async def generate(self, prompt: str, **kwargs) -> str:
        # Use google.genai
        ...

# agents/models/openai_adapter.py
class OpenAIAdapter(ModelAdapter):
    ...

# Configuration
MODEL_ADAPTER = os.getenv("MODEL_ADAPTER", "gemini")  # gemini | openai | anthropic
```

**ADR Needed:** ADR-009-model-adapter-contract.md -- **Created and accepted.**

### 2.3 Add Agent Runtime Telemetry

**Current:** Manual trace calls (`begin_tool_call`, `end_tool_call`).

**Recommendation:** Implement ADK runtime hooks for automatic telemetry.

```python
# agents/telemetry/adk_hooks.py
from google.adk.events import Event

def on_agent_start(event: Event):
    trace.record_event("AGENT_START", event.model_dump())

def on_tool_call(event: Event):
    trace.record_event("TOOL_CALL", event.model_dump())

def on_agent_end(event: Event):
    trace.record_event("AGENT_END", event.model_dump())

# Wire into LlmAgent
agent = LlmAgent(
    ...,
    hooks={
        "on_start": on_agent_start,
        "on_tool_call": on_tool_call,
        "on_end": on_agent_end,
    }
)
```

---

## 3. A2A (Agent-to-Agent) Recommendations

### 3.1 Add Persistent Relay Backend

**Current:** `InMemoryA2ARelay` loses messages on restart.

**Recommendation:** Add Redis-backed relay for production deployments.

```python
# services/registry/src/registry/a2a_relay_redis.py
import redis.asyncio as redis
from shared.a2a.schemas import A2AMessageEnvelope

class RedisA2ARelay:
    """Redis-backed A2A relay for production deployments."""
    
    def __init__(self, redis_url: str):
        self._redis = redis.from_url(redis_url)
        self._ttl_seconds = 86400 * 7  # 7 days
    
    async def send(self, message: A2AMessageEnvelope) -> bool:
        # Use Redis Streams or Lists
        await self._redis.xadd(
            f"a2a:inbox:{message.to_library}",
            {"message": message.model_dump_json()},
        )
        await self._redis.setex(
            f"a2a:seen:{message.id}",
            self._ttl_seconds,
            "1",
        )
        return True
```

**Configuration:**
```yaml
# docker-compose.yml
A2A_RELAY_BACKEND=${A2A_RELAY_BACKEND:-memory}  # memory | redis
REDIS_URL=${REDIS_URL:-redis://localhost:6379/0}
```

**ADR Needed:** ADR-010-a2a-relay-backend.md

### 3.2 Add A2A Message Encryption

**Current:** Payloads are JSON-serialized but not encrypted.

**Recommendation:** Add optional payload encryption for sensitive ILL data.

```python
# shared/a2a/crypto.py
from cryptography.fernet import Fernet

class A2AEncryption:
    def __init__(self, key: bytes):
        self._fernet = Fernet(key)
    
    def encrypt_payload(self, payload: dict) -> str:
        return self._fernet.encrypt(
            json.dumps(payload).encode()
        ).decode()
    
    def decrypt_payload(self, encrypted: str) -> dict:
        return json.loads(
            self._fernet.decrypt(encrypted.encode())
        )

# Usage in a2a_client.py
message = A2AMessageEnvelope(
    payload=encryptor.encrypt_payload(sensitive_payload)
    if ENCRYPTION_ENABLED else payload,
)
```

### 3.3 Implement A2A Dead Letter Queue

**Current:** Failed messages are lost after retry exhaustion.

**Recommendation:** Add DLQ for failed A2A messages.

```python
# services/ill/src/ill/a2a_client.py - Enhanced
async def send_a2a_message(...) -> dict[str, Any]:
    try:
        return await _do_send()
    except RetryExhausted:
        # Send to DLQ for manual inspection
        await _send_to_dlq(message, reason="retry_exhausted")
        raise
```

---

## 4. Microservices Recommendations

### 4.1 Implement Event Sourcing for ILL

**Current:** State machine transitions are logged to audit trail, but events are not first-class.

**Recommendation:** Implement event sourcing for ILL workflows.

```python
# shared/events/base.py
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

@dataclass
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    aggregate_type: str
    timestamp: datetime
    payload: dict

# services/ill/src/ill/events.py
class ILLRequestCreated(DomainEvent):
    event_type: Literal["ill_request_created"] = "ill_request_created"
    payload: ILLRequestPayload

class ILLRequestApproved(DomainEvent):
    event_type: Literal["ill_request_approved"] = "ill_request_approved"
    payload: ApprovalPayload

# Event store
class EventStore:
    async def append(self, event: DomainEvent) -> None:
        # Store to dedicated events table
        ...
    
    async def get_events(self, aggregate_id: str) -> list[DomainEvent]:
        # Replay events to reconstruct state
        ...
```

**Benefits:**
- Complete audit history
- Temporal queries ("What did the system look like yesterday?")
- Easier debugging
- Foundation for event-driven notifications

**ADR Needed:** ADR-011-event-sourcing-for-ill.md

### 4.2 Add CQRS for Catalog Queries

**Current:** Catalog read/write use same models.

**Recommendation:** Separate read models for complex catalog queries.

```python
# services/catalog/src/catalog/read_models.py
@dataclass
class BookSearchResult:
    """Optimized for search results (denormalized)."""
    id: str
    title: str
    author: str
    available_copies: int
    total_copies: int
    # No need for full book model

class CatalogQueryService:
    """Read-only service for catalog queries."""
    
    async def search(self, query: str) -> list[BookSearchResult]:
        # Use Elasticsearch or materialized view
        ...
```

### 4.3 Implement Database per Service (v2.2)

**Current:** SQLite databases are service-local but schema is coupled.

**Recommendation:** Formalize database-per-service with schema ownership.

```
services/
  catalog/
    migrations/           # Catalog owns its schema
      001_initial.sql
      002_add_indexes.sql
    src/catalog/models.py # SQLModel definitions
  
  circulation/
    migrations/           # Circulation owns its schema
    src/circulation/models.py
  
  ill/
    migrations/           # ILL owns its schema
    src/ill/models.py
```

**Shared Schema Strategy:**
- Use `shared/schemas.py` for API contracts only
- Each service owns its database models
- Cross-service joins happen at API level, not DB level

---

## 5. Testing Recommendations

### 5.1 MCP Integration Tests

**Current:** `test_processor_mcp.py` uses mocks.

**Recommendation:** Add live MCP integration tests.

```python
# agents/tests/integration/test_mcp_live.py
@pytest.mark.asyncio
@pytest.mark.mcp_live  # Custom marker
async def test_catalog_mcp_search():
    """Test against real MCP server subprocess."""
    async with MCPConnectionManager().toolset_context("catalog") as toolset:
        result = await toolset.search_books(query="Greyhorn")
        data = json.loads(result)
        assert data["total"] > 0
```

### 5.2 A2A Chaos Tests

**Current:** Basic fault injection exists.

**Recommendation:** Add network-level chaos tests.

```python
# tests/scenarios/test_a2a_chaos_network.py
@pytest.mark.asyncio
async def test_a2a_partition_recovery():
    """Simulate network partition between libraries."""
    with network_partition("catalog-hanno", "registry"):
        # Send A2A message
        # Verify queued but not delivered
        pass
    
    # Remove partition
    # Verify message delivered
```

### 5.3 ADK Agent E2E Tests

**Current:** Agent tests use mocks or bypass ADK runtime.

**Recommendation:** Add true E2E agent tests.

```python
# agents/tests/e2e/test_front_desk_e2e.py
@pytest.mark.asyncio
@pytest.mark.e2e
@pytest.mark.requires_api_key
async def test_front_desk_catalog_search():
    """Full agent + LLM + services integration."""
    agent = create_front_desk_agent()
    
    response = await run_agent_text(
        agent=agent,
        message="Find me books by Maren Greyhorn",
    )
    
    assert "Greyhorn" in response
    # Verify tool was actually called via trace
```

---

## 6. Implementation Priority

### v2.1 (Cross-Model Comparison)

| Priority | Task | Effort | Impact | Status |
|----------|------|--------|--------|--------|
| P0 | Model adapter interface | 3d | Enables v2.1 | **Done (v2.2)** |
| P0 | ADR-009 model contract | 1d | Documentation | **Done (v2.2)** |
| P1 | Standardize sub-agent pattern | 2d | Code quality | **Done (v2.2)** |
| P1 | ADR-008 delegation pattern | 1d | Documentation | **Done (v2.2)** |
| P2 | Remove dead TOOLS JSON | 1d | Tech debt | |

### v2.2 (RL Data Productization)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P0 | Trajectory export format | 3d | RL requirement |
| P1 | Preference-pair builder | 2d | RL requirement |
| P2 | MCP-first tool refactor | 5d | Architecture |
| P2 | ADR-007 MCP transport | 1d | Documentation |

### v3.0 (Ecosystem Maturity)

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| P1 | Event sourcing for ILL | 5d | Auditability |
| P2 | Redis A2A relay | 3d | Production |
| P2 | ADR-010 relay backend | 1d | Documentation |
| P3 | A2A encryption | 3d | Security |
| P3 | CQRS for catalog | 5d | Performance |

---

## 7. Architecture Decision Records to Create

| ADR ID | Title | Priority | Target Version | Status |
|--------|-------|----------|----------------|--------|
| ADR-007 | MCP Transport Strategy | P1 | v2.2 | **Accepted** |
| ADR-008 | Agent Delegation Pattern | P0 | v2.1 | **Accepted (v2.2)** |
| ADR-009 | Model Adapter Contract | P0 | v2.1 | **Accepted (v2.2)** |
| ADR-010 | A2A Relay Backend Selection | P2 | v2.2 | Pending |
| ADR-011 | Event Sourcing for ILL | P2 | v3.0 | Pending |

**Template Location:** `docs/architecture/adr/ADR_TEMPLATE.md`

---

## 8. Code Quality Checklist

### Before v2.1 Release

- [x] All new code uses sub-agent pattern (no new class-based wrappers) -- **Done in v2.2**
- [x] Model adapter interface implemented with Gemini adapter -- **Done in v2.2** (`build_model_adapter().to_adk_model_ref()`)
- [ ] Dead `*_TOOLS` JSON removed or deprecated
- [x] ADR-008 and ADR-009 written and approved -- **Done in v2.2**
- [x] CI passes with 620+ tests -- **649 passing as of v2.5**

### Before v2.2 Release

- [ ] MCP-first tools working in staging
- [ ] Trajectory export pipeline tested
- [ ] Redis A2A relay tested
- [ ] ADR-007 and ADR-010 written

### Before v3.0 Release

- [ ] Event sourcing for ILL complete
- [ ] Database-per-service formalized
- [ ] A2A encryption optional feature
- [ ] All ADRs up to ADR-011 complete

---

## 9. Long-term Evolution (v3.0+)

### 9.1 Potential Architecture Shifts

| Current | Future | Trigger |
|---------|--------|---------|
| Sync HTTP calls | Async event-driven | >100 req/s |
| In-memory state | Event-sourced | Multi-region |
| Single model | Multi-model ensemble | Accuracy requirements |
| SQLite | PostgreSQL | Concurrent write load |

### 9.2 Research Areas

1. **Federated Learning**: Can we train models without centralizing library data?
2. **Differential Privacy**: Can we benchmark while protecting patron privacy?
3. **Model Distillation**: Can we create smaller, faster agents for edge deployment?

---

## Appendix A: Migration Examples

### A.1 FrontDeskAgent to Sub-Agent Pattern

```python
# BEFORE (v2.0)
class FrontDeskAgent:
    def __init__(self):
        self._catalog_agent = CatalogAgent()
        self._circulation_agent = CirculationAgent()
        self._agent = LlmAgent(
            tools=[
                FunctionTool(func=self._catalog_search),
                FunctionTool(func=self._circulation_action),
            ]
        )

# AFTER (v2.1+)
def create_front_desk_agent() -> LlmAgent:
    return LlmAgent(
        name="front_desk_agent",
        instruction=PROMPT,
        sub_agents=[
            create_catalog_agent(),
            create_circulation_agent(),
        ],
    )
```

### A.2 HTTP Tool to MCP Tool

```python
# BEFORE (v2.0)
@with_retry(max_attempts=3)
async def search_books(query: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CATALOG_URL}/books", params={"q": query})
        return response.json()

# AFTER (v2.2)
async def search_books(query: str) -> dict:
    async with MCPConnectionManager().toolset_context("catalog") as toolset:
        result = await toolset.search_books(query=query)
        return json.loads(result)
```

---

## References

- [MCP Specification](https://modelcontextprotocol.io/)
- [Google ADK Documentation](https://google.github.io/adk-docs/)
- [A2A Protocol](A2A_PROTOCOL.md)
- [ADR Index](adr/INDEX.md)
- [v2.1 Execution Plan](../status/V2_1_EXECUTION_PLAN.md)

---

*Last Updated: 2026-02-09*
