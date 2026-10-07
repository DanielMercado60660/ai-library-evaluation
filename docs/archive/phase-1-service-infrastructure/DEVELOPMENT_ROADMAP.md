# Development Roadmap - AI Librarian Evaluation System

**Last Updated:** 2026-02-02  
**Current Phase:** Phase 0 Complete ✅ → Phase 1 Starting 🎯

---

## Project Vision

Build a multi-agent library system where AI agents manage library operations across a network of libraries, using the A2A (Agent-to-Agent) protocol for inter-library communication.

### Core Philosophy

**Incremental Complexity:** Build and validate each layer before adding the next
- Services → Integration → Single Agent → Multi-Agent → Full System

**Test-Driven Development:** Every component has comprehensive tests
- Currently: 200+ tests across three services

**Real-World Modeling:** Simulate actual library operations
- Checkouts, holds, ILL requests, patron management

---

## Phase 0: Service Layer ✅ COMPLETE

**Goal:** Build core library services with TDD approach

### Deliverables ✅
- **Catalog Service** - Books, instances, holdings management
- **Circulation Service** - Checkouts, holds, fines, patron management
- **ILL Service** - Inter-library loan (borrowing & lending)

### Metrics
- **3 services** fully implemented
- **200+ tests** passing (74 ILL, 60+ Circulation, 60+ Catalog)
- **24 API endpoints** total
- **Mock integration patterns** documented

### Key Achievements
- Complete TDD workflow demonstrated
- Data isolation security verified (ILL inbound endpoints)
- Comprehensive documentation (README per service)
- Production-ready code with proper error handling

**Status:** ✅ Can move to Phase 1

---

## Phase 1: Functional Library System 🎯 CURRENT

**Goal:** Get all services working together as an integrated system that can be manually tested end-to-end.

### Objectives

1. **Cross-Service Integration**
   - Services communicate via HTTP
   - ILL queries Circulation for patron verification
   - Circulation queries Catalog for book availability
   - Catalog updates propagate to dependent services

2. **Manual Testing Capability**
   - Run all three services together
   - Trace complete workflows manually
   - Verify data flows correctly
   - Catch integration issues early

3. **Shared Infrastructure**
   - Service discovery mechanism
   - Shared test data (patrons, books)
   - Consistent IDs across services
   - Database seeding scripts

### Deliverables

- [ ] Service registry for discovery
- [ ] HTTP client helper for inter-service calls
- [ ] Implement 5-10 key integration points
- [ ] Manual testing scripts (trace workflows)
- [ ] Docker Compose setup (optional but recommended)
- [ ] Integration tests spanning multiple services
- [ ] Shared test data (hanno_patrons.json, etc.)

### Key Integration Points

**High Priority:**
1. ILL → Circulation: Verify patron exists and is in good standing
2. Circulation → Catalog: Check book availability before checkout
3. Circulation → Catalog: Reserve instance for checkout
4. Circulation → Catalog: Update instance status (available ↔ checked_out)
5. ILL → Catalog: Verify book not available locally before ILL request

**Medium Priority:**
6. ILL → Catalog: Query holdings for inbound requests
7. Circulation → Catalog: Check holds when item returned
8. Catalog → Circulation: Get patron info for display

### Success Criteria

- [ ] All three services run simultaneously
- [ ] Complete checkout workflow works end-to-end
- [ ] Complete ILL borrowing workflow works
- [ ] Complete ILL lending workflow works
- [ ] Manual test script traces all flows
- [ ] No mock data - real cross-service queries
- [ ] Error handling works (service down, not found, etc.)

### Testing Strategy

**Manual Testing:**
```bash
# Start all services
docker-compose up
# Or manually in 3 terminals

# Run test workflows
python scripts/test_complete_checkout.py
python scripts/test_ill_borrow.py
python scripts/test_ill_lend.py
```

**Integration Tests:**
```bash
pytest tests/integration/test_cross_service.py
```

### Timeline Estimate
- **2-4 days** if going with simple HTTP integration
- **1 week** if building proper Docker infrastructure first

**Recommended:** Start simple (HTTP + manual testing), add infrastructure once working

**Status:** Ready to start - see [NEXT_STEPS.md](NEXT_STEPS.md) for detailed implementation plan

---

## Phase 2: Single Agent + MCP 🔄 NEXT

**Goal:** One AI agent interacting with one library's services via Model Context Protocol (MCP).

### What This Enables

- AI agent can search catalog
- Agent can check out books for patrons
- Agent can handle patron questions
- Agent can process ILL requests
- Agent uses tools to interact with services

### Architecture

```
┌─────────────────────────────────────────────────┐
│          ADK Agent (Claude/GPT/etc)             │
│  "Please check out 'Pachyderm Algorithms' for   │
│   patron John Doe"                              │
└─────────────────┬───────────────────────────────┘
                  │
                  │ MCP Protocol
                  ▼
┌─────────────────────────────────────────────────┐
│           MCP Server                            │
│  Tools:                                         │
│  - search_books()                               │
│  - checkout_book()                              │
│  - create_ill_request()                         │
│  - check_patron_status()                        │
└─────────────────┬───────────────────────────────┘
                  │
                  │ HTTP Calls
                  ▼
┌─────────────────────────────────────────────────┐
│  Catalog | Circulation | ILL Services           │
└─────────────────────────────────────────────────┘
```

### Deliverables

- [ ] ADK agent setup (Google Agent Development Kit)
- [ ] MCP server implementation
  - [ ] Tool definitions for each service operation
  - [ ] HTTP → Service call wrappers
- [ ] Agent workflows
  - [ ] Patron interaction workflows
  - [ ] Search and checkout workflow
  - [ ] ILL request workflow
  - [ ] Hold management workflow
- [ ] Multi-model testing
  - [ ] Test with Claude (Sonnet, Opus)
  - [ ] Test with GPT-4
  - [ ] Test with Gemini
  - [ ] Compare performance/accuracy
- [ ] Agent memory system (basic)
  - [ ] Conversation history
  - [ ] Context retention
  - [ ] Patron preferences

### Key Workflows to Implement

1. **Patron Book Search**
   - Agent searches catalog
   - Presents results to patron
   - Checks availability

2. **Book Checkout**
   - Verify patron eligibility
   - Check book availability
   - Reserve instance
   - Create checkout record

3. **ILL Request**
   - Verify book not available locally
   - Check patron eligibility
   - Create ILL request
   - Track status

4. **Patron Account Management**
   - Check current checkouts
   - Check holds
   - View fines
   - Renew books

### Success Criteria

- [ ] Agent can successfully complete 10+ library tasks
- [ ] Agent maintains context across conversation
- [ ] Agent handles errors gracefully
- [ ] Works with multiple LLM backends
- [ ] Response time < 5 seconds for simple queries
- [ ] Agent never makes unauthorized actions

### Timeline Estimate
- **1-2 weeks** for basic agent + MCP setup
- **2-3 weeks** for all workflows + multi-model testing

**Status:** Waiting on Phase 1 completion

---

## Phase 3: Multi-Library A2A Communication 🔄 FUTURE

**Goal:** Multiple library agents communicating with each other using A2A protocol.

### Architecture

```
┌──────────────────┐        A2A Protocol       ┌──────────────────┐
│ Hanno Memorial   │◄─────────────────────────►│ Mastodon Inst.   │
│ Library Agent    │                            │ Library Agent    │
│                  │                            │                  │
│ - Catalog        │                            │ - Catalog        │
│ - Circulation    │                            │ - Circulation    │
│ - ILL            │                            │ - ILL            │
└──────────────────┘                            └──────────────────┘
         ▲                                               ▲
         │                                               │
         │              A2A Broker/Registry              │
         └───────────────────┬───────────────────────────┘
                             │
                             ▼
                  ┌──────────────────┐
                  │ Mammoth Valley   │
                  │ Library Agent    │
                  └──────────────────┘
```

### What This Enables

- Agent-to-agent communication
- Automated ILL request handling
- Cross-library book discovery
- Standardized message formats
- Asynchronous status updates

### Implementation Strategy

**Test Each Library Independently First:**
1. Create second library (Mastodon Institute)
   - Mirror of Hanno Memorial
   - Different data (patrons, books)
   - Same services structure

2. Create third library (Mammoth Valley)
   - Another mirror
   - Different specialization

3. Test each library's agent independently
   - Verify all workflows work
   - Ensure data isolation
   - Test patron interactions

**Then Connect via A2A:**
1. Implement A2A protocol
2. Build broker/registry service
3. Enable library discovery
4. Test inter-library workflows

### Deliverables

- [ ] A2A protocol specification
- [ ] A2A broker/registry service
- [ ] Second library agent (Mastodon Institute)
- [ ] Third library agent (Mammoth Valley)
- [ ] Inter-library communication patterns
- [ ] Automated ILL workflows
- [ ] Status synchronization
- [ ] Error handling across library boundaries

### Key Workflows

1. **Automated ILL Request**
   - Hanno patron requests book
   - Hanno agent queries network for availability
   - Mastodon agent responds with availability
   - Hanno agent creates ILL request
   - Mastodon agent approves and ships

2. **Cross-Library Search**
   - Patron searches Hanno catalog
   - Not found locally
   - Agent queries partner libraries
   - Returns results from network

3. **Status Updates**
   - Mastodon ships book
   - Status update sent to Hanno
   - Hanno notifies patron
   - Patron notified when received

### Success Criteria

- [ ] Three independent library agents working
- [ ] Agents can discover each other
- [ ] Automated ILL request/fulfillment workflow
- [ ] Proper data isolation (no patron info leaks)
- [ ] Async messaging working
- [ ] Error recovery (library offline, etc.)

### Timeline Estimate
- **2-3 weeks** for A2A protocol + broker
- **1 week** per additional library agent
- **1 week** for integration testing

**Status:** Depends on Phase 2 completion

---

## Phase 4: Full System 🔄 FUTURE

**Goal:** Complete system with frontend, evaluation framework, and production features.

### Components

#### 4.1 Frontend UI
- Patron-facing interface
- Librarian admin interface
- Real-time status updates
- Search and discovery
- Account management

#### 4.2 Evaluation Framework
- Agent performance metrics
- Success rate tracking
- Response time monitoring
- Error analysis
- Model comparison

#### 4.3 Chaos Testing
- Service failures
- Network partitions
- Database issues
- Load testing
- Recovery testing

#### 4.4 Notifications & Messaging
- Email notifications (book ready, overdue, etc.)
- Async message queue
- Push notifications
- SMS integration (optional)

#### 4.5 Patron Distribution
- Distribute test patrons across libraries
- Realistic usage patterns
- Different patron categories
- Cross-library borrowing patterns

#### 4.6 Memory System
- Enhanced conversation memory
- Long-term patron preferences
- Learning from interactions
- Context management
- Google ADK memory features

#### 4.7 Production Features
- Authentication & authorization
- Rate limiting
- Monitoring & logging
- Backup & recovery
- Scalability improvements

### Timeline Estimate
- **4-6 weeks** for complete Phase 4

**Status:** Future work after Phases 1-3

---

## Summary Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0: Service Layer | 2-3 weeks | ✅ Complete |
| Phase 1: Functional System | 1 week | 🎯 Current |
| Phase 2: Single Agent + MCP | 2-3 weeks | 🔄 Next |
| Phase 3: Multi-Library A2A | 4-5 weeks | 🔄 Future |
| Phase 4: Full System | 4-6 weeks | 🔄 Future |
| **TOTAL** | **~14-18 weeks** | |

---

## Current Priority

**NOW:** Phase 1 - Functional Library System

See [NEXT_STEPS.md](NEXT_STEPS.md) for detailed implementation plan.

**Key Decision Points:**
1. Integration pattern (HTTP vs shared DB vs message queue)
2. Service discovery approach
3. Data strategy (separate vs shared)
4. Development environment (manual vs Docker)

**Recommended First Steps:**
1. Create simple service registry
2. Implement 2-3 key cross-service calls
3. Build manual test script
4. Trace complete checkout workflow
5. Verify everything works end-to-end

Then expand to more integration points and add proper infrastructure.

---

## Long-Term Vision

A fully functional multi-agent library network where:
- Each library has its own AI agent
- Agents communicate via standardized protocols
- Patrons interact naturally with agents
- Cross-library resource sharing is seamless
- System handles failures gracefully
- Performance is measurable and improvable
- Real-world library workflows are modeled accurately

**The system serves as an evaluation framework for:**
- Multi-agent coordination
- Protocol adherence (A2A)
- Real-world task completion
- Model comparison
- Agent reliability
- System resilience

---

**Next:** Review [NEXT_STEPS.md](NEXT_STEPS.md) and decide on integration approach!
