# Next Steps: AI Library Project

**Last Updated:** 2026-02-03
**Current Phase:** Phase 2 Complete (ADK Migration) - Phase 3 Ready

---

## Project Status Summary

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 0 | Service Layer (Catalog, Circulation, ILL) | ✅ Complete |
| Phase 1 | Service Integration (HTTP, Docker Compose) | ✅ Complete |
| Phase 2 | ADK Migration & Agents | ✅ Complete |
| Phase 3 | Multi-Library A2A Communication | 🎯 Next |
| Phase 4 | Evaluation & Chaos Testing | 📋 Planned |

---

## What's Been Accomplished

### Phase 2 Achievements (ADK Migration)

**Core Infrastructure:**
- ✅ All agents migrated to ADK `LlmAgent` patterns
- ✅ `DatabaseSessionService` for persistent session management
- ✅ MCP connection manager with proper lifecycle handling
- ✅ Resilience utilities (retry decorators, circuit breakers)

**Workflow Agents (SequentialAgent):**
- ✅ ILL Approval Workflow (3 steps)
- ✅ Inbound Loan Workflow (4 steps)
- ✅ Checkout Workflow (4 steps)

**Testing:**
- ✅ 109 tests passing (34 unit + 75 integration)
- ✅ Processor ↔ MCP integration tests
- ✅ Workflow execution tests
- ✅ Session persistence tests

**Files Created/Modified:**
- `agents/src/agents/session/adk_session_service.py`
- `agents/src/agents/mcp/connection_manager.py`
- `agents/src/agents/utils/resilience.py`
- `agents/src/agents/workflows/` (3 workflows)
- `agents/tests/integration/` (complete test suite)

---

## Recommended Next Steps

### Option A: Complete Phase 2 Polish (Lower Risk)

Before moving to Phase 3, consider completing these Phase 2 enhancements:

1. **Frontend Integration**
   - Connect Angular frontend to agent API
   - Test chat interface with real agent responses
   - Verify session management in UI

2. **E2E Testing with Docker Compose**
   - Create `docker-compose.test.yml`
   - Full stack tests (frontend → agent → MCP → services → DB)
   - CI/CD pipeline setup

3. **Multi-Model Testing**
   - Test agents with different LLM backends (Claude, GPT-4, Gemini)
   - Compare performance/accuracy
   - Document model-specific behaviors

4. **Memory System (Basic)**
   - Implement conversation summarization
   - Add patron preference tracking
   - Test context retention across sessions

**Effort:** 1-2 weeks

---

### Option B: Begin Phase 3 (Multi-Library A2A)

Start building the multi-library network:

1. **Create Second Library (Mastodon Institute)**
   - Clone Hanno Memorial structure
   - Generate unique catalog data (STEM focus)
   - Generate unique patron data
   - Deploy as separate Docker service set

2. **Implement A2A Protocol**
   - Follow specification in [A2A_PROTOCOL.md](../architecture/A2A_PROTOCOL.md)
   - Create A2A message schemas
   - Implement discovery service
   - Build broker/registry

3. **Connect Libraries via A2A**
   - Enable library discovery
   - Implement inter-library ILL workflows
   - Test cross-library searches
   - Verify data isolation (patron privacy)

4. **Automated ILL Workflows**
   - Hanno patron requests book → Mastodon agent responds
   - Automated approval/denial based on policies
   - Status synchronization across libraries

**Effort:** 3-4 weeks

---

### Option C: Jump to Evaluation (High Value for Research)

If the goal is research output, consider skipping to evaluation:

1. **Define Evaluation Metrics**
   - Tool use accuracy
   - Hallucination detection
   - Error handling quality
   - Response latency

2. **Create Test Scenarios**
   - Happy path workflows
   - Edge cases (unavailable books, blocked patrons)
   - Adversarial inputs (trick questions, prompt injection)
   - System failures (service down, timeout)

3. **Run Multi-Model Comparison**
   - Claude Sonnet vs Opus
   - GPT-4 vs GPT-4o
   - Gemini Pro vs Ultra
   - Document behavioral differences

4. **Analyze Results**
   - Which models hallucinate?
   - Which use tools correctly?
   - How do they handle errors?
   - Write up findings

**Effort:** 2-3 weeks

---

## Technical Debt to Address

These items can be tackled alongside any option:

1. **datetime.utcnow() Deprecation**
   - Replace with `datetime.now(UTC)` across codebase
   - Update all timestamp handling

2. **ADK API Stability**
   - Monitor for ADK updates
   - Update imports if APIs change

3. **Test Coverage Gaps**
   - Add E2E tests
   - Add negative test cases
   - Improve workflow edge case coverage

---

## Decision Points

**Questions to Consider:**

1. **What's the primary goal?**
   - Research paper → Option C (Evaluation)
   - Production system → Option A (Polish)
   - Feature demonstration → Option B (Multi-Library)

2. **Timeline constraints?**
   - Demo soon → Option A or C
   - Longer runway → Option B

3. **Team bandwidth?**
   - Solo → Option A or C
   - Team → Option B (parallelizable)

---

## Quick Start Commands

```bash
# Run all agent tests
cd ai-library/agents && pytest tests/ -v

# Start services with Docker
cd ai-library && docker-compose up -d

# Test agent API
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for books about elephants", "session_id": "test-123"}'

# Run ILL processor manually
cd ai-library/agents && python -m agents.ill_approval_agent
```

---

## Related Documentation

- [AGENT_INTEGRATION_GUIDE.md](AGENT_INTEGRATION_GUIDE.md) - How to work with ADK agents
- [A2A_PROTOCOL.md](../architecture/A2A_PROTOCOL.md) - Agent-to-agent communication spec
- [EVALUATION.md](../architecture/EVALUATION.md) - Evaluation framework
- [MEMORY_SYSTEM.md](../architecture/MEMORY_SYSTEM.md) - Memory architecture
