# ADK Implementation Review & Improvement Plan

## Overview

Full refactor of the agents section using Google ADK best practices (2026), including:
- Complete migration of all agents to ADK `LlmAgent` patterns
- DatabaseSessionService for persistent session management
- WorkflowAgents for multi-step operations (ILL approval, checkout)
- Comprehensive error handling and MCP lifecycle management

---

## Current State Analysis

### Agent Inventory

| Agent | Implementation | Issues |
|-------|----------------|--------|
| `FrontDeskAgent` | `google.genai` direct | No ADK patterns, manual conversation history |
| `CatalogAgent` | `google.genai` direct | Stateless, no session management |
| `CirculationAgent` | `google.genai` direct | Stateless, no session management |
| `ILLApprovalAgent` | ADK `LlmAgent` | No SessionService, placeholder processor |
| `InboundLoanAgent` | ADK `LlmAgent` | No SessionService, placeholder processor |

### Key Issues Identified

1. **Inconsistent framework** - Mix of `google.genai` and `google.adk.agents.LlmAgent`
2. **No ADK SessionService** - Custom `ChatSessionManager` instead of ADK's built-in
3. **Placeholder processors** - `process_pending_queue()` methods are stubs
4. **No WorkflowAgents** - Multi-step operations not using ADK workflow patterns
5. **Basic error handling** - No retry logic or graceful degradation
6. **MCP lifecycle issues** - No async context managers for connections

---

## Implementation Plan (Full Refactor)

### Phase 1: ADK Session Infrastructure with DatabaseSessionService

**Create persistent session service:**
- New file: `agents/src/agents/session/adk_session_service.py`
- Use ADK's `DatabaseSessionService` for persistent sessions across restarts
- Configure SQLite/PostgreSQL backend (match existing service DB patterns)
- Add patron context management and session state helpers

```python
from google.adk.sessions import DatabaseSessionService

class LibrarySessionService:
    def __init__(self, db_url: str = "sqlite:///./db/sessions.db"):
        self._service = DatabaseSessionService(connection_string=db_url)

    async def get_or_create_session(self, session_id: str, patron_id: str = None):
        session = await self._service.get_session(session_id)
        if not session:
            session = await self._service.create_session(
                session_id=session_id,
                state={"patron_id": patron_id, "history": []}
            )
        return session
```

**Changes to:**
- [chat.py](ai-library/agents/src/agents/chat.py) - Replace custom `ChatSessionManager` with ADK `DatabaseSessionService`

### Phase 2: Migrate HTTP-based Agents to ADK

**Migrate FrontDeskAgent:**
- Convert from `google.genai` to ADK `LlmAgent`
- Use sub-agent pattern for delegation to Catalog/Circulation agents
- Add `output_key` for state passing

**Migrate CatalogAgent & CirculationAgent:**
- Convert to ADK `LlmAgent` with MCP toolsets
- Add proper tool definitions using `McpToolset`

**Changes to:**
- [front_desk.py](ai-library/agents/src/agents/front_desk.py)
- [catalog_agent.py](ai-library/agents/src/agents/catalog_agent.py)
- [circulation_agent.py](ai-library/agents/src/agents/circulation_agent.py)

### Phase 3: Complete Processor Implementations

**ILLApprovalProcessor:**
- Implement full `process_pending_queue()` method
- Integrate with existing `evaluate_request_for_approval()` function
- Add MCP tool calls for queue fetch, approval/denial execution

**InboundLoanProcessor:**
- Implement full `process_pending_queue()` method
- Integrate with existing `evaluate_inbound_loan()` function

**Changes to:**
- [ill_approval_agent.py](ai-library/agents/src/agents/ill_approval_agent.py) lines 229-263
- [inbound_loan_agent.py](ai-library/agents/src/agents/inbound_loan_agent.py) lines 210-241

### Phase 4: WorkflowAgent Implementation

**ILL Approval Workflow using SequentialAgent:**
- New file: `agents/src/agents/workflows/ill_approval_workflow.py`
- Steps: fetch queue → check eligibility → evaluate policy → execute decision → audit
- Use `output_key` for state passing between steps
- Use instruction templating (`{pending_requests}`, `{decisions}`)

```python
from google.adk.agents import SequentialAgent, LlmAgent

class ILLApprovalWorkflow(SequentialAgent):
    def __init__(self, mcp_manager):
        super().__init__(
            name="ill_approval_workflow",
            sub_agents=[
                LlmAgent(name="fetch", instruction="Fetch pending queue",
                        tools=[mcp_manager.ill_tools], output_key="pending_requests"),
                LlmAgent(name="evaluate", instruction="For each in {pending_requests}, check eligibility",
                        tools=[mcp_manager.circulation_tools], output_key="decisions"),
                LlmAgent(name="execute", instruction="Execute {decisions}: approve/deny/skip",
                        tools=[mcp_manager.ill_tools], output_key="results"),
            ]
        )
```

**Checkout Workflow using SequentialAgent:**
- New file: `agents/src/agents/workflows/checkout_workflow.py`
- Steps: verify patron → check availability → execute checkout → notify
- Handle edge cases (holds queue, fines block, unavailable)

**Inbound Loan Workflow:**
- New file: `agents/src/agents/workflows/inbound_loan_workflow.py`
- Steps: fetch queue → check availability → evaluate lending policy → execute

**New files:**
- `agents/src/agents/workflows/__init__.py`
- `agents/src/agents/workflows/ill_approval_workflow.py`
- `agents/src/agents/workflows/checkout_workflow.py`
- `agents/src/agents/workflows/inbound_loan_workflow.py`

### Phase 5: MCP Lifecycle Management

**Create connection manager:**
- New file: `agents/src/agents/mcp/connection_manager.py`
- Async context managers for proper toolset lifecycle
- Centralized MCP service configurations

### Phase 6: Error Handling & Resilience

**Add retry/circuit breaker utilities:**
- New file: `agents/src/agents/utils/resilience.py`
- Decorator for exponential backoff retries
- Simple circuit breaker for service calls

**Apply to existing tools:**
- Wrap HTTP calls in catalog_tools.py and circulation_tools.py

---

## Critical Files

### Existing Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `agents/src/agents/ill_approval_agent.py` | 3, 4 | Complete processor, add workflow |
| `agents/src/agents/inbound_loan_agent.py` | 3, 4 | Complete processor, add workflow |
| `agents/src/agents/front_desk.py` | 2 | Migrate to ADK LlmAgent with sub-agents |
| `agents/src/agents/chat.py` | 1 | Replace with ADK DatabaseSessionService |
| `agents/src/agents/catalog_agent.py` | 2 | Migrate to ADK LlmAgent |
| `agents/src/agents/circulation_agent.py` | 2 | Migrate to ADK LlmAgent |
| `agents/src/agents/tools/catalog_tools.py` | 6 | Add retry decorators |
| `agents/src/agents/tools/circulation_tools.py` | 6 | Add retry decorators |

### New Files to Create

| File | Phase | Purpose |
|------|-------|---------|
| `agents/src/agents/session/__init__.py` | 1 | Session module |
| `agents/src/agents/session/adk_session_service.py` | 1 | DatabaseSessionService wrapper |
| `agents/src/agents/mcp/__init__.py` | 5 | MCP module |
| `agents/src/agents/mcp/connection_manager.py` | 5 | MCP lifecycle management |
| `agents/src/agents/utils/__init__.py` | 6 | Utils module |
| `agents/src/agents/utils/resilience.py` | 6 | Retry/circuit breaker utilities |
| `agents/src/agents/workflows/__init__.py` | 4 | Workflows module |
| `agents/src/agents/workflows/ill_approval_workflow.py` | 4 | ILL approval SequentialAgent |
| `agents/src/agents/workflows/checkout_workflow.py` | 4 | Checkout SequentialAgent |
| `agents/src/agents/workflows/inbound_loan_workflow.py` | 4 | Inbound loan SequentialAgent |

---

## Implementation Order

1. **Phase 5 first** - MCP lifecycle management (foundation for all phases)
2. **Phase 1** - Session infrastructure with DatabaseSessionService
3. **Phase 6** - Error handling utilities
4. **Phase 2** - Migrate HTTP-based agents to ADK
5. **Phase 3** - Complete processor implementations
6. **Phase 4** - Add WorkflowAgents for multi-step operations

---

## Verification

1. **Unit tests**: Run existing tests
   ```bash
   cd ai-library/agents && pytest tests/unit/ -v
   ```

2. **Integration tests**: Test agent + MCP server interactions
   ```bash
   # Start MCP servers first
   python -m catalog.mcp_server &
   python -m circulation.mcp_server &
   python -m ill.mcp_server &
   pytest tests/integration/ -v
   ```

3. **Manual testing**: Run the FastAPI server
   ```bash
   uvicorn agents.api:app --reload
   # POST to http://localhost:8000/chat with {"message": "...", "session_id": "..."}
   ```

4. **Processor testing**: Verify ILL approval decisions
   ```python
   processor = ILLApprovalProcessor(ill_tools, circulation_tools)
   results = await processor.process_pending_queue()
   # Check: results["approved"], results["denied"], results["skipped"]
   ```

5. **Workflow testing**: Test SequentialAgent state passing
   ```python
   workflow = ILLApprovalWorkflow(mcp_manager)
   result = await workflow.run(session=session, input_data={})
   # Verify session.state["pending_requests"], ["decisions"], ["results"]
   ```

---

## ADK Best Practices Applied

1. **DatabaseSessionService** for persistent session management
2. **SequentialAgent** for multi-step workflows with state passing
3. **MCPToolset** with proper async lifecycle management
4. **Parent-child agent patterns** (FrontDesk → Catalog/Circulation sub-agents)
5. **Instruction templating** (`{var}` syntax) for dynamic context
6. **Error handling** with retry decorators and circuit breakers
7. **output_key** for state passing between sequential agents
8. **Tool filtering** to limit MCP tools exposed to each agent

---

# Phase 7: Integration & E2E Testing Plan

## Implementation Status: ✅ COMPLETE

All implementation phases (1-6) have been completed:
- ✅ MCP lifecycle management (`mcp/connection_manager.py`)
- ✅ Session infrastructure (`session/adk_session_service.py`)
- ✅ Resilience utilities (`utils/resilience.py`)
- ✅ Agent migrations (FrontDesk, Catalog, Circulation to ADK)
- ✅ Processor implementations (ILLApproval, InboundLoan)
- ✅ WorkflowAgents (ILLApproval, InboundLoan, Checkout workflows)

---

## Testing Strategy

### Test Pyramid for AI Library Agents

```
         ┌─────────────────┐
         │     E2E Tests   │  Docker-compose full stack
         │   (Few, Slow)   │
         ├─────────────────┤
         │  Integration    │  Agent ↔ MCP interaction
         │  (Medium)       │  Direct tool calls, DB patching
         ├─────────────────┤
         │   Unit Tests    │  99 tests ✅ (policy evaluation)
         │  (Many, Fast)   │
         └─────────────────┘
```

---

## Phase 7A: Integration Tests

### New Files to Create

| File | Purpose |
|------|---------|
| `agents/tests/integration/__init__.py` | Integration test module |
| `agents/tests/integration/conftest.py` | Shared fixtures for integration tests |
| `agents/tests/integration/test_processor_mcp.py` | Processor ↔ MCP tool tests |
| `agents/tests/integration/test_workflow_execution.py` | Workflow agent execution tests |
| `agents/tests/integration/test_session_persistence.py` | Session service integration tests |

### Test Infrastructure Pattern

**conftest.py fixtures:**
```python
@pytest_asyncio.fixture
async def test_engine():
    """In-memory SQLite for test isolation."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(test_engine):
    """Patch MCP servers to use test database."""
    with patch("catalog.mcp_server.async_engine", test_engine):
        with patch("circulation.mcp_server.async_engine", test_engine):
            with patch("ill.mcp_server.async_engine", test_engine):
                async with async_session_maker() as session:
                    yield session

@pytest_asyncio.fixture
async def mock_ill_tools(db_session):
    """Mock ILL MCP tools using direct imports."""
    from ill.mcp_server import (
        get_pending_outbound_queue,
        approve_ill_request,
        deny_ill_request,
    )
    return {
        "get_pending_outbound_queue": get_pending_outbound_queue,
        "approve_ill_request": approve_ill_request,
        "deny_ill_request": deny_ill_request,
    }
```

### Test Cases: Processor ↔ MCP Integration

**test_processor_mcp.py:**

| Test Class | Test Cases |
|------------|------------|
| `TestILLApprovalProcessorMCP` | |
| | `test_fetches_pending_queue_from_mcp` - Processor calls MCP tool, receives queue |
| | `test_checks_patron_eligibility_via_mcp` - Patron check uses circulation MCP |
| | `test_approves_request_via_mcp` - Approval writes to ILL service |
| | `test_denies_request_via_mcp` - Denial writes to ILL service |
| | `test_full_queue_processing` - Complete queue: fetch → evaluate → approve/deny |
| | `test_handles_mcp_tool_error` - Graceful handling of MCP failures |
| `TestInboundLoanProcessorMCP` | |
| | `test_fetches_inbound_queue_from_mcp` - Fetches pending inbound loans |
| | `test_checks_availability_via_mcp` - Catalog availability check |
| | `test_reserves_instance_via_mcp` - Reserves book for approved loan |
| | `test_full_inbound_processing` - Complete flow with real MCP calls |

### Test Cases: Workflow Agent Execution

**test_workflow_execution.py:**

| Test Class | Test Cases |
|------------|------------|
| `TestILLApprovalWorkflow` | |
| | `test_workflow_state_passing` - output_key passes data between steps |
| | `test_fetch_step_populates_pending_requests` - First step stores queue |
| | `test_evaluate_step_produces_decisions` - Second step creates decisions list |
| | `test_execute_step_calls_approval_tools` - Third step executes decisions |
| `TestInboundLoanWorkflow` | |
| | `test_four_step_workflow` - All 4 steps execute in sequence |
| | `test_availability_enriches_loans` - Catalog data added to loan objects |
| `TestCheckoutWorkflow` | |
| | `test_verify_patron_step` - Patron eligibility checked first |
| | `test_blocked_patron_stops_workflow` - Workflow stops on ineligible patron |
| | `test_successful_checkout_generates_confirmation` - Full happy path |

### Test Cases: Session Persistence

**test_session_persistence.py:**

| Test Class | Test Cases |
|------------|------------|
| `TestLibrarySessionService` | |
| | `test_creates_new_session` - New session with patron_id |
| | `test_retrieves_existing_session` - Get by session_id works |
| | `test_session_expiration` - Expired sessions return None |
| | `test_session_history_persists` - Conversation history saved |
| `TestChatSessionIntegration` | |
| | `test_chat_session_uses_adk_session` - ChatSession wraps LibrarySession |
| | `test_async_session_creation` - Async factory method works |
| | `test_session_cleanup` - Expired sessions removed |

---

## Phase 7B: E2E Tests (Docker-based)

### Setup Required

**docker-compose.test.yml:**
```yaml
services:
  catalog:
    build: services/catalog
    ports: ["8001:8000"]
    healthcheck: ...

  circulation:
    build: services/circulation
    ports: ["8002:8000"]
    depends_on: [catalog]

  ill:
    build: services/ill
    ports: ["8003:8000"]
    depends_on: [catalog, circulation]

  agents:
    build: agents
    ports: ["8000:8000"]
    depends_on: [catalog, circulation, ill]
    environment:
      - CATALOG_SERVICE_URL=http://catalog:8000
      - CIRCULATION_SERVICE_URL=http://circulation:8000
      - ILL_SERVICE_URL=http://ill:8000
```

**E2E Test Cases:**

| Test | Description |
|------|-------------|
| `test_chat_searches_catalog` | POST /chat "Find books by Hemingway" → agent returns catalog results |
| `test_chat_checks_patron_fines` | POST /chat "What are my fines?" → agent returns circulation data |
| `test_ill_approval_workflow_e2e` | Full ILL request approval via agent + MCP + service |
| `test_checkout_workflow_e2e` | Patron checkout via agent workflow |

---

## Implementation Order

1. **Create integration test directory structure**
2. **Write conftest.py with shared fixtures**
3. **Implement processor MCP tests** (highest value)
4. **Implement workflow execution tests**
5. **Implement session persistence tests**
6. **Run all tests and fix issues**
7. **(Optional) Set up E2E with docker-compose**

---

## Verification Commands

```bash
# 1. Run existing unit tests (should pass)
cd ai-library/agents && pytest tests/unit/ -v

# 2. Run new integration tests
cd ai-library/agents && pytest tests/integration/ -v

# 3. Run all agent tests with coverage
cd ai-library/agents && pytest tests/ -v --cov=agents --cov-report=term-missing

# 4. (Optional) E2E with docker-compose
docker-compose -f docker-compose.test.yml up -d
pytest tests/e2e/ -v
docker-compose -f docker-compose.test.yml down
```

---

## Critical Implementation Details

### MCP Tool Mocking Strategy

**Direct import approach** (recommended for speed):
```python
# Import MCP tool functions directly
from ill.mcp_server import get_pending_outbound_queue, approve_ill_request

# Call as async functions (no HTTP, no subprocess)
result = await get_pending_outbound_queue()
data = json.loads(result)
```

**Why this works:**
- MCP servers define tools as async functions
- Tests patch the database engine to use in-memory SQLite
- Direct calls are faster and more reliable than subprocess/HTTP

### Database Patching Pattern

```python
# Patch ALL services that share data
with patch("catalog.mcp_server.async_engine", test_engine):
    with patch("circulation.mcp_server.async_engine", test_engine):
        with patch("ill.mcp_server.async_engine", test_engine):
            # Now all MCP tools use same in-memory DB
            pass
```

### Test Data Factories

```python
@pytest.fixture
def ill_request_factory(db_session):
    """Factory for creating ILL requests."""
    async def create(**overrides):
        defaults = {
            "id": f"req-{uuid4()}",
            "patron_id": "patron-001",
            "status": "pending",
            ...
        }
        request = ILLRequestModel(**{**defaults, **overrides})
        db_session.add(request)
        await db_session.commit()
        return request
    return create
```
