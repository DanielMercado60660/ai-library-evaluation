# Agent Integration Guide: ADK & MCP for ILL System

**Status:** Planning Phase
**Target:** Phase 2 - Agent-Driven ILL Operations
**Prerequisites:** Phase 1.5 Complete ✅ (Approval workflows, state machine, async tasks, registry)

## Overview

This guide outlines the strategy for building intelligent agents using the **Anthropic Development Kit (ADK)** and **Model Context Protocol (MCP)** to drive Inter-Library Loan operations in the AI Library system.

### Goals

1. **Agent-Driven Approvals** - Intelligent agents review and approve/deny ILL requests based on patron context, library metrics, and policy rules
2. **MCP Database Access** - Single shared database access via MCP servers for all agents
3. **Autonomous ILL Operations** - Agents handle complete workflows from request to return
4. **A2A Protocol Foundation** - Prepare for agent-to-agent communication between libraries

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Agent Layer (ADK)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ ILL Approval     │  │ Patron Service   │  │ Catalog      │ │
│  │ Agent            │  │ Agent            │  │ Agent        │ │
│  │                  │  │                  │  │              │ │
│  │ - Review queue   │  │ - Check patrons  │  │ - Search     │ │
│  │ - Check policy   │  │ - Manage fines   │  │ - Holdings   │ │
│  │ - Approve/deny   │  │ - Handle blocks  │  │              │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│           │                     │                     │         │
└───────────┼─────────────────────┼─────────────────────┼─────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                  MCP Server Layer (Database Access)              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ ILL MCP Server   │  │ Circulation MCP  │  │ Catalog MCP  │ │
│  │                  │  │ Server           │  │ Server       │ │
│  │ Resources:       │  │                  │  │              │ │
│  │ - ill://queue    │  │ Resources:       │  │ Resources:   │ │
│  │ - ill://request  │  │ - patron://list  │  │ - book://    │ │
│  │ - ill://audit    │  │ - checkout://    │  │ - instance://│ │
│  │                  │  │                  │  │              │ │
│  │ Tools:           │  │ Tools:           │  │ Tools:       │ │
│  │ - approve_ill    │  │ - check_patron   │  │ - search     │ │
│  │ - deny_ill       │  │ - create_checkout│  │ - check_avail│ │
│  │ - query_audit    │  │ - calculate_fines│  │              │ │
│  └──────────────────┘  └──────────────────┘  └──────────────┘ │
│           │                     │                     │         │
└───────────┼─────────────────────┼─────────────────────┼─────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Database Layer (SQLite)                       │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │ ill.db       │  │circulation.db│  │ catalog.db   │         │
│  │              │  │              │  │              │         │
│  │ - ill_reqs   │  │ - patrons    │  │ - books      │         │
│  │ - inbound    │  │ - checkouts  │  │ - instances  │         │
│  │ - audit_trail│  │ - fines      │  │ - holdings   │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

## MCP Server Design

### Why MCP Over HTTP APIs?

**Advantages:**
1. **Direct Database Access** - No HTTP overhead, faster queries
2. **Resource-Oriented** - Natural mapping to library entities (books, patrons, requests)
3. **Tool Composition** - Agents can combine MCP tools seamlessly
4. **Streaming Support** - Real-time updates for long-running operations
5. **Type Safety** - Structured schemas for all resources and tools

**When to Use HTTP APIs:**
- Cross-service operations (still use FastAPI routes for this)
- External integrations (A2A protocol)
- Web UI/frontend access
- Public APIs for partners

### MCP Server Structure

Each service should expose an MCP server alongside its HTTP API:

```
services/ill/
├── src/ill/
│   ├── main.py           # FastAPI HTTP server
│   ├── mcp_server.py     # MCP server (NEW)
│   ├── mcp_tools.py      # MCP tool definitions (NEW)
│   ├── mcp_resources.py  # MCP resource definitions (NEW)
│   └── ...
├── Dockerfile
└── Dockerfile.mcp        # MCP server container (NEW)
```

### ILL MCP Server Specification

**Resources:**

```python
# ill://queue/pending/outbound
# Returns enriched approval queue for outbound requests
{
  "uri": "ill://queue/pending/outbound",
  "mimeType": "application/json",
  "content": [
    {
      "id": "ill-req-001",
      "book_title": "...",
      "patron_context": {...},
      "library_context": {...},
      "days_pending": 2
    }
  ]
}

# ill://queue/pending/inbound
# Returns enriched approval queue for inbound loans

# ill://request/{request_id}
# Returns specific ILL request with full details

# ill://audit/{request_id}
# Returns audit trail for a request
```

**Tools:**

```python
# approve_ill_request
{
  "name": "approve_ill_request",
  "description": "Approve an outbound ILL request for a patron",
  "inputSchema": {
    "type": "object",
    "properties": {
      "request_id": {"type": "string"},
      "librarian_id": {"type": "string"},
      "notes": {"type": "string"}
    },
    "required": ["request_id", "librarian_id"]
  }
}

# deny_ill_request
# Similar structure for denials

# query_audit_trail
{
  "name": "query_audit_trail",
  "description": "Query audit trail for compliance/debugging",
  "inputSchema": {
    "type": "object",
    "properties": {
      "request_id": {"type": "string"},
      "loan_id": {"type": "string"},
      "from_date": {"type": "string", "format": "date-time"},
      "to_date": {"type": "string", "format": "date-time"}
    }
  }
}
```

### Circulation MCP Server Specification

**Resources:**

```python
# patron://{patron_id}
# Returns patron details with checkout history, fines, blocks

# checkout://active?patron_id={patron_id}
# Returns active checkouts for a patron

# fine://patron/{patron_id}
# Returns unpaid fines for a patron
```

**Tools:**

```python
# check_patron_eligibility
{
  "name": "check_patron_eligibility",
  "description": "Check if patron is eligible for ILL (no blocks, under fine limit)",
  "inputSchema": {
    "type": "object",
    "properties": {
      "patron_id": {"type": "string"}
    },
    "required": ["patron_id"]
  }
}

# create_checkout (for auto-checkout on ILL receipt)
# calculate_fines
# apply_block
```

### Catalog MCP Server Specification

**Resources:**

```python
# book://{book_id}
# Returns book metadata

# instance://{instance_id}
# Returns instance details (status, barcode, location)

# search://books?isbn={isbn}
# Search results for books
```

**Tools:**

```python
# search_books
# check_availability
# reserve_instance
# release_instance
```

## Agent Design Patterns

### 1. ILL Approval Agent

**Responsibility:** Review pending ILL requests and make approval decisions

**Decision Criteria:**
- Patron eligibility (no blocks, fines under limit)
- Library metrics (fulfillment rate, response time)
- Priority level (urgent, high, normal, low)
- Justification quality
- Request age (days pending)

**Agent Flow:**
```
1. Query ill://queue/pending/outbound via MCP
2. For each request:
   a. Check patron eligibility via circulation MCP
   b. Review library metrics from enriched context
   c. Apply policy rules (see below)
   d. Make decision: approve or deny
   e. Call approve_ill_request or deny_ill_request tool
3. Log decisions and reasoning
```

**Policy Rules (Example):**
```python
def should_approve_outbound(request, patron, library):
    # Auto-deny blocked patrons
    if patron.is_blocked:
        return False, "Patron account blocked"

    # Auto-deny high fines
    if patron.total_fines >= 10.00:
        return False, "Outstanding fines exceed $10.00"

    # Check library metrics
    if library.fulfillment_rate < 0.70:
        return False, f"Library has low fulfillment rate ({library.fulfillment_rate})"

    # Prioritize urgent requests
    if request.priority == "urgent" and request.days_pending > 1:
        return True, "Urgent request approved"

    # Standard approval for good standing
    if patron.total_fines < 5.00 and library.fulfillment_rate >= 0.85:
        return True, "Patron in good standing, reliable library"

    # Default: manual review needed
    return None, "Requires manual review"
```

### 2. Inbound Loan Agent

**Responsibility:** Review inbound loan requests from partner libraries

**Decision Criteria:**
- Instance availability
- Partner library metrics (on-time return rate)
- Book value/rarity (from catalog)
- Current demand for the book

**Agent Flow:**
```
1. Query ill://queue/pending/inbound via MCP
2. For each loan request:
   a. Check instance availability via catalog MCP
   b. Review partner library metrics
   c. Assess book value/demand
   d. Make decision: approve or deny
   e. Call approve_inbound_loan or deny_inbound_loan tool
3. Track lending patterns
```

### 3. Patron Service Agent

**Responsibility:** Handle patron-facing queries and issues

**Capabilities:**
- Check account status
- Explain fine calculations
- Provide ILL request status updates
- Handle block appeals

**Agent Flow:**
```
1. Receive patron query (via chat/API)
2. Identify intent (check status, pay fine, appeal block, etc.)
3. Query relevant MCP resources (patron://, checkout://, ill://request/)
4. Formulate helpful response
5. Offer next actions
```

## Implementation Roadmap

### Phase 2.1: MCP Server Setup (Week 1) ✅ COMPLETE

**Tasks:**
- [x] Create MCP server for ILL service
  - Resources: ill://queue/pending/outbound, ill://queue/pending/inbound, ill://request/{id}, ill://audit/{id}
  - Tools: approve_ill_request, deny_ill_request, approve_inbound_loan, deny_inbound_loan, query_audit_trail, get_queue_statistics
  - File: `services/ill/src/ill/mcp_server.py`
- [x] Create MCP server for Circulation service
  - Resources: patron://{id}, patron://{id}/summary, checkout://active, fine://patron/{id}
  - Tools: check_patron_eligibility, apply_block, remove_block, calculate_patron_fines, get_overdue_checkouts
  - File: `services/circulation/src/circulation/mcp_server.py`
- [x] Create MCP server for Catalog service
  - Resources: book://{id}, instance://{id}, search://books, catalog://availability
  - Tools: search_books, check_availability, reserve_instance, release_instance, get_books_by_stratum
  - File: `services/catalog/src/catalog/mcp_server.py`

**Deliverables:**
- ✅ 3 MCP servers (FastMCP-based) embedded in services
- ✅ Resource and tool schemas in code docstrings
- ⏳ Integration tests for MCP endpoints (pending)

### Phase 2.2: ILL Approval Agent (Week 2) ✅ COMPLETE

**Tasks:**
- [x] Build ILL Approval Agent using Google ADK
  - McpToolset integration with ILL and Circulation MCP servers
  - Policy rules engine with auto-approve/deny/skip logic
  - Decision logging via audit trail
  - File: `agents/src/agents/ill_approval_agent.py`
- [x] Create agent prompts and instructions
  - System prompt with complete policy rules
  - Auto-approve: fines < $5, fulfillment >= 85%, urgent priority
  - Auto-deny: blocked, fines >= $10, fulfillment < 70%
  - Manual review: edge cases
- [ ] Test approval workflows
  - Happy path (approve eligible requests)
  - Denial scenarios (blocked patrons, high fines)
  - Edge cases (manual review needed)

**Deliverables:**
- ✅ Working ILL Approval Agent with ADK + MCP
- ⏳ Test suite with 20+ scenarios (pending)
- ✅ Agent decision logs via audit trail

### Phase 2.3: Inbound Loan Agent (Week 2-3) ✅ COMPLETE

**Tasks:**
- [x] Build Inbound Loan Agent
  - McpToolset integration with ILL and Catalog MCP servers
  - Instance availability checking via catalog MCP
  - Partner library reliability assessment
  - Book value/rarity consideration (stratum-based)
  - File: `agents/src/agents/inbound_loan_agent.py`
- [x] Lending policy implementation
  - Rare book protection (Stratum I, single copies)
  - Demand-based decisions
  - Partner reputation scoring (on-time return rate)

**Deliverables:**
- ✅ Working Inbound Loan Agent with ADK + MCP
- ⏳ Integration with ILL Approval Agent (pending)
- ⏳ Analytics on lending decisions (pending)

### Phase 2.4: Multi-Agent Orchestration (Week 3-4)

**Tasks:**
- [ ] Agent coordination layer
  - Handoffs between agents
  - Shared context management
  - Conflict resolution
- [ ] A2A Protocol foundation
  - Agent-to-agent messaging format
  - Partner library agent discovery
  - Protocol specification draft

**Deliverables:**
- Multi-agent system handling full ILL lifecycle
- A2A protocol spec (v0.1)
- End-to-end demo scenarios

## Best Practices

### MCP Server Development

1. **Resource Naming** - Use hierarchical URIs (`service://type/id`)
2. **Tool Granularity** - One tool per atomic operation
3. **Schema Validation** - Strict input/output schemas
4. **Error Handling** - Descriptive error messages for agents
5. **Performance** - Cache frequently accessed resources
6. **Security** - Validate all inputs, sanitize queries

### Agent Development

1. **Clear Instructions** - Explicit system prompts with examples
2. **Policy Transparency** - Document decision rules
3. **Logging** - Log all decisions with reasoning
4. **Graceful Degradation** - Handle MCP server failures
5. **Human in the Loop** - Escalate complex cases
6. **Testing** - Cover edge cases, adversarial inputs

### Database Access Patterns

**DO:**
- ✅ Use MCP for read-heavy operations (querying, searching)
- ✅ Use MCP for atomic writes (approve one request)
- ✅ Implement connection pooling in MCP servers
- ✅ Use read replicas if scaling needed

**DON'T:**
- ❌ Don't expose raw SQL through MCP tools
- ❌ Don't bypass state machine validation
- ❌ Don't allow bulk updates without transaction safety
- ❌ Don't cache stale data (use TTLs)

## Success Criteria

### Phase 2 Complete When:

1. **MCP Infrastructure** ✅
   - 3 MCP servers (ILL, Circulation, Catalog) running
   - All resources and tools accessible
   - Integration tests passing

2. **Agent Capabilities** ✅
   - ILL Approval Agent handles 90%+ of decisions autonomously
   - Inbound Loan Agent approves/denies with 85%+ accuracy
   - Decision logs show clear reasoning

3. **Performance** ✅
   - Approval queue processed in <5 seconds per request
   - MCP resource queries <100ms p95
   - No database connection leaks

4. **Reliability** ✅
   - Agents recover from MCP server failures
   - State machine prevents invalid transitions
   - Audit trail captures all agent actions

5. **A2A Foundation** ✅
   - Protocol spec drafted
   - Agent-to-agent communication patterns defined
   - Ready for multi-library network testing

## Resources

**ADK Documentation:**
- [Anthropic Developer Console](https://console.anthropic.com/)
- ADK Quickstart Guide
- Agent Builder SDK

**MCP Documentation:**
- [Model Context Protocol Spec](https://modelcontextprotocol.io/)
- MCP Python SDK
- MCP Server Examples

**Related Docs:**
- [ILL Service README](../../services/ill/README.md)
- [State Machine Implementation](../../services/ill/src/ill/state_machine.py)
- [A2A Protocol Spec](../architecture/A2A_PROTOCOL.md)

---

**Next Steps:**
1. Review this guide with the team
2. Set up MCP development environment
3. Create first MCP server (ILL service)
4. Build minimal ILL Approval Agent
5. Iterate based on results
