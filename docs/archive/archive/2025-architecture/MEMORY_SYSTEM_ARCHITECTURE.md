## Doc Header
- Doc Status: Exploratory
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Memory architecture exploration
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: world-data-governance

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Memory System Architecture: Agent Interaction Patterns

> **Research Question**: What is the best architecture for AI agents to interact with stateful memory in a distributed library system?

This document explores architectural approaches for agent-memory interaction, treating this as an open design question to be validated through implementation and evaluation.

---

## Table of Contents

1. [The Core Problem](#the-core-problem)
2. [Architectural Options](#architectural-options)
3. [Option 1: Memory as MCP Server](#option-1-memory-as-mcp-server)
4. [Option 2: Memory as HTTP Microservice](#option-2-memory-as-http-microservice)
5. [Option 3: Memory as Context Pre-Loader](#option-3-memory-as-context-pre-loader)
6. [Option 4: Event-Driven Memory](#option-4-event-driven-memory)
7. [Option 5: Hybrid ADK + MCP + A2A](#option-5-hybrid-adk--mcp--a2a)
8. [Comparison Matrix](#comparison-matrix)
9. [Recommendation Engine Integration](#recommendation-engine-integration)
10. [Evaluation Criteria](#evaluation-criteria)
11. [Implementation Strategy](#implementation-strategy)

---

## The Core Problem

### What We're Solving

AI agents need to:
1. **Read** patron preferences and past interactions
2. **Write** new interactions and learned preferences
3. **Reason** about what to recommend based on memory
4. **Respect** privacy boundaries and consent levels
5. **Operate** across distributed services (Hanno, Greytusk, Mastodon)
6. **Degrade gracefully** when memory service is unavailable

### Key Questions

| Question | Why It Matters |
|----------|----------------|
| **Who owns the memory?** | Is it agent state or a separate service? |
| **When is memory accessed?** | Pre-conversation, during, or post-conversation? |
| **How does memory flow?** | Push (events) or pull (queries)? |
| **What protocol?** | MCP, HTTP, A2A, or hybrid? |
| **How do agents discover capabilities?** | Static vs. dynamic schema |
| **What happens on failure?** | Cache? Queue? Degrade? |

### Design Constraints

From your existing architecture:

```
✓ Already using: Google ADK (not just genai SDK)
✓ Already using: MCP for local resource access
✓ Already using: A2A for cross-library communication
✓ Already using: Microservices (Catalog, Circulation at :8001, :8002)
✓ Need to add: Memory as another architectural component
```

---

## Architectural Options

We'll explore five approaches, each with different trade-offs for:
- **Complexity** (implementation difficulty)
- **Flexibility** (agent autonomy)
- **Performance** (latency, throughput)
- **Testability** (evaluation scenarios)
- **Failure modes** (resilience)

---

## Option 1: Memory as MCP Server

### Concept

Memory exposes an MCP server that agents discover and interact with like other resources (catalog, filesystem).

### Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    FRONT DESK AGENT (ADK)                     │
│                                                               │
│  Agent discovers available resources:                         │
│  - mcp://catalog/books                                        │
│  - mcp://circulation/checkouts                                │
│  - mcp://memory/episodic                                      │
│  - mcp://memory/semantic                                      │
│                                                               │
└───────────────────────────┬──────────────────────────────────┘
                            │
                      MCP Protocol
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                   MEMORY MCP SERVER                           │
│                                                               │
│  Resources:                                                   │
│  - memory://patron/{patron_id}/profile                        │
│  - memory://patron/{patron_id}/recent_sessions                │
│  - memory://patron/{patron_id}/preferences                    │
│                                                               │
│  Tools:                                                       │
│  - recall_context(patron_id, query)                           │
│  - store_interaction(patron_id, summary, facts)               │
│  - update_preferences(patron_id, preferences)                 │
│  - get_recommendations(patron_id, context)                    │
│                                                               │
│  Prompts:                                                     │
│  - summarize_session(conversation_history)                    │
│  - extract_preferences(conversation_history)                  │
│  - generate_recommendation_explanation(patron, books)         │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Agent Interaction Pattern

```python
# Agent discovers memory resources dynamically
async def chat(self, message: str, patron_id: str):
    # 1. Agent discovers available resources via MCP
    resources = await self.mcp_client.list_resources()
    # Returns: ['mcp://memory/episodic', 'mcp://catalog/books', ...]

    # 2. Agent can read memory as a resource
    if patron_id:
        memory_content = await self.mcp_client.read_resource(
            f"memory://patron/{patron_id}/profile"
        )
        # Returns: JSON with preferences, past interactions

    # 3. Agent reasons about the query
    response = await self.adk_agent.process(
        message,
        context={"patron_memory": memory_content}
    )

    # 4. Agent can call memory tools if needed
    if "recommendation" in message.lower():
        recommendations = await self.mcp_client.call_tool(
            "get_recommendations",
            {"patron_id": patron_id, "context": message}
        )

    # 5. Agent can use memory prompts for compression
    session_summary = await self.mcp_client.get_prompt(
        "summarize_session",
        {"conversation": self.conversation_history}
    )

    return response
```

### MCP Server Implementation

```python
# services/memory/mcp_server.py

from mcp.server import Server
from mcp.types import Resource, Tool, Prompt
from typing import List, Dict


class MemoryMCPServer(Server):
    """MCP server exposing memory operations to agents."""

    def __init__(self, memory_store):
        super().__init__(name="memory")
        self.store = memory_store

    async def list_resources(self) -> List[Resource]:
        """Expose memory as discoverable resources."""
        return [
            Resource(
                uri="memory://episodic",
                name="Recent Patron Interactions",
                description="Searchable log of recent patron sessions",
                mimeType="application/json"
            ),
            Resource(
                uri="memory://semantic",
                name="Patron Profiles",
                description="Long-term patron preferences and patterns",
                mimeType="application/json"
            ),
            Resource(
                uri="memory://working",
                name="Session Context",
                description="Current conversation state",
                mimeType="application/json"
            )
        ]

    async def read_resource(self, uri: str) -> Dict:
        """Read memory resource by URI."""

        # Parse URI: memory://patron/{patron_id}/profile
        parts = uri.split("/")

        if "profile" in parts:
            patron_id = parts[3]
            return await self.store.get_semantic_memory(patron_id)

        elif "recent_sessions" in parts:
            patron_id = parts[3]
            return await self.store.get_recent_sessions(patron_id, limit=5)

        # ... handle other URI patterns

    async def list_tools(self) -> List[Tool]:
        """Expose memory operations as tools."""
        return [
            Tool(
                name="recall_context",
                description="Search patron memory for relevant context given a query",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patron_id": {"type": "string"},
                        "query": {"type": "string", "description": "What to search for in memory"},
                        "max_results": {"type": "integer", "default": 3}
                    },
                    "required": ["patron_id", "query"]
                }
            ),
            Tool(
                name="get_recommendations",
                description="Generate book recommendations based on patron preferences",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patron_id": {"type": "string"},
                        "context": {"type": "string", "description": "Current conversation context"},
                        "count": {"type": "integer", "default": 5}
                    },
                    "required": ["patron_id"]
                }
            ),
            Tool(
                name="store_interaction",
                description="Store a compressed interaction summary after session ends",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patron_id": {"type": "string"},
                        "session_id": {"type": "string"},
                        "summary": {"type": "string"},
                        "key_facts": {"type": "array", "items": {"type": "string"}},
                        "books_discussed": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["patron_id", "session_id", "summary"]
                }
            ),
            Tool(
                name="update_preferences",
                description="Update learned preferences for a patron",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patron_id": {"type": "string"},
                        "preferences": {
                            "type": "object",
                            "description": "Preference updates (genres, authors, strata)"
                        }
                    },
                    "required": ["patron_id", "preferences"]
                }
            )
        ]

    async def call_tool(self, name: str, arguments: Dict) -> Dict:
        """Execute memory tool."""

        if name == "recall_context":
            return await self._recall_context(
                patron_id=arguments["patron_id"],
                query=arguments["query"],
                max_results=arguments.get("max_results", 3)
            )

        elif name == "get_recommendations":
            return await self._get_recommendations(
                patron_id=arguments["patron_id"],
                context=arguments.get("context"),
                count=arguments.get("count", 5)
            )

        # ... other tools

    async def list_prompts(self) -> List[Prompt]:
        """Expose memory-related prompt templates."""
        return [
            Prompt(
                name="summarize_session",
                description="Compress a conversation into a summary for storage",
                arguments=[
                    {"name": "conversation", "description": "Full conversation history", "required": True}
                ]
            ),
            Prompt(
                name="extract_preferences",
                description="Extract patron preferences from conversation",
                arguments=[
                    {"name": "conversation", "description": "Conversation to analyze", "required": True}
                ]
            ),
            Prompt(
                name="explain_recommendation",
                description="Generate an explanation for why a book was recommended",
                arguments=[
                    {"name": "patron_profile", "description": "Patron preferences", "required": True},
                    {"name": "recommended_books", "description": "Books being recommended", "required": True}
                ]
            )
        ]

    async def get_prompt(self, name: str, arguments: Dict) -> str:
        """Get a filled prompt template."""

        if name == "summarize_session":
            conversation = arguments["conversation"]
            return f"""Summarize this library interaction in 2-3 sentences:

Conversation:
{conversation}

Focus on:
- What the patron was looking for
- Books discussed or borrowed
- Preferences mentioned

Summary:"""

        # ... other prompts


# Start MCP server
async def run_memory_mcp_server():
    from shared.memory_firestore import FirestoreMemoryStore

    memory_store = FirestoreMemoryStore()
    server = MemoryMCPServer(memory_store)

    await server.run(transport="stdio")  # or "sse" for HTTP
```

### Pros & Cons

**Pros:**
- ✅ **Dynamic discovery** - Agents learn what memory operations exist at runtime
- ✅ **Schema evolution** - Can add new memory tools without updating agents
- ✅ **Standard protocol** - MCP is becoming an industry standard
- ✅ **Resource abstraction** - Memory looks like any other resource (catalog, files)
- ✅ **Composable** - Can combine with other MCP servers

**Cons:**
- ❌ **MCP implementation complexity** - Need to build full MCP server
- ❌ **Not widely adopted yet** - MCP is newer, fewer examples
- ❌ **Local only?** - MCP typically for local resources, may need extensions for distributed
- ❌ **Agent complexity** - Agent must know when to query memory vs. other resources

### When to Use

- **If**: You want maximum flexibility and future-proofing
- **If**: You're already using MCP extensively for other resources
- **If**: You value dynamic schema discovery
- **If**: You want memory to feel like a "native" resource to agents

---

## Option 2: Memory as HTTP Microservice

### Concept

Memory is a traditional REST API microservice that agents call via HTTP, just like Catalog (:8001) and Circulation (:8002).

### Architecture

```
┌────────────────────────────────────────────────────────┐
│              FRONT DESK AGENT (ADK)                     │
│                                                         │
│  - Uses ADK for orchestration                           │
│  - Makes HTTP calls to microservices                    │
│  - Handles responses                                    │
│                                                         │
└────────────────┬────────────────┬──────────────────────┘
                 │                │
          HTTP   │         HTTP   │
                 │                │
     ┌───────────▼──┐     ┌───────▼──────┐
     │  Catalog     │     │ Circulation  │
     │  :8001       │     │ :8002        │
     └──────────────┘     └──────────────┘
                 │
          HTTP   │
                 │
         ┌───────▼──────────┐
         │   Memory         │
         │   :8004          │
         │                  │
         │ GET  /memory/profile/{patron_id}
         │ POST /memory/recall
         │ POST /memory/store
         │ GET  /memory/recommendations/{patron_id}
         └──────────────────┘
```

### API Specification

```yaml
# services/memory/openapi.yaml

openapi: 3.0.0
info:
  title: Memory Service API
  version: 1.0.0
  description: Patron memory and preference management

servers:
  - url: http://localhost:8004
    description: Local development

paths:
  /memory/profile/{patron_id}:
    get:
      summary: Get patron profile (semantic memory)
      parameters:
        - name: patron_id
          in: path
          required: true
          schema:
            type: string
      responses:
        200:
          description: Patron profile
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/PatronProfile'
        404:
          description: Patron not found

  /memory/recall:
    post:
      summary: Semantic search over recent interactions
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                patron_id:
                  type: string
                query:
                  type: string
                  description: What to search for in memory
                max_results:
                  type: integer
                  default: 5
                max_age_days:
                  type: integer
                  default: 90
      responses:
        200:
          description: Relevant memories
          content:
            application/json:
              schema:
                type: object
                properties:
                  memories:
                    type: array
                    items:
                      $ref: '#/components/schemas/EpisodicMemory'

  /memory/store:
    post:
      summary: Store interaction summary
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              properties:
                patron_id:
                  type: string
                session_id:
                  type: string
                summary:
                  type: string
                key_facts:
                  type: array
                  items:
                    type: string
                books_discussed:
                  type: array
                  items:
                    type: string
      responses:
        201:
          description: Memory stored

  /memory/recommendations/{patron_id}:
    get:
      summary: Get personalized book recommendations
      parameters:
        - name: patron_id
          in: path
          required: true
          schema:
            type: string
        - name: context
          in: query
          schema:
            type: string
          description: Current conversation context
        - name: count
          in: query
          schema:
            type: integer
            default: 5
      responses:
        200:
          description: Recommended books
          content:
            application/json:
              schema:
                type: object
                properties:
                  recommendations:
                    type: array
                    items:
                      $ref: '#/components/schemas/Recommendation'

components:
  schemas:
    PatronProfile:
      type: object
      properties:
        patron_id:
          type: string
        profile_level:
          type: string
          enum: [anonymous, registered, active, personalized]
        inferred_preferences:
          type: object
        explicit_preferences:
          type: object
        consent:
          type: object

    EpisodicMemory:
      type: object
      properties:
        id:
          type: string
        session_id:
          type: string
        created_at:
          type: string
          format: date-time
        summary:
          type: string
        key_facts:
          type: array
          items:
            type: string
        similarity:
          type: number
          description: Semantic similarity score

    Recommendation:
      type: object
      properties:
        book_id:
          type: string
        title:
          type: string
        author:
          type: string
        confidence:
          type: number
        explanation:
          type: string
          description: Why this book is recommended
```

### Agent Integration

```python
# agents/src/agents/memory_client.py

import httpx
from typing import Dict, List, Optional


class MemoryClient:
    """HTTP client for memory service."""

    def __init__(self, base_url: str = "http://localhost:8004"):
        self.base_url = base_url
        self.client = httpx.AsyncClient()

    async def get_profile(self, patron_id: str) -> Optional[Dict]:
        """Get patron profile."""
        response = await self.client.get(f"{self.base_url}/memory/profile/{patron_id}")

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    async def recall_context(
        self,
        patron_id: str,
        query: str,
        max_results: int = 5
    ) -> List[Dict]:
        """Search recent memories."""
        response = await self.client.post(
            f"{self.base_url}/memory/recall",
            json={
                "patron_id": patron_id,
                "query": query,
                "max_results": max_results
            }
        )
        response.raise_for_status()
        return response.json()["memories"]

    async def store_interaction(
        self,
        patron_id: str,
        session_id: str,
        summary: str,
        key_facts: List[str],
        books_discussed: List[str]
    ):
        """Store interaction summary."""
        response = await self.client.post(
            f"{self.base_url}/memory/store",
            json={
                "patron_id": patron_id,
                "session_id": session_id,
                "summary": summary,
                "key_facts": key_facts,
                "books_discussed": books_discussed
            }
        )
        response.raise_for_status()

    async def get_recommendations(
        self,
        patron_id: str,
        context: Optional[str] = None,
        count: int = 5
    ) -> List[Dict]:
        """Get personalized recommendations."""
        params = {"count": count}
        if context:
            params["context"] = context

        response = await self.client.get(
            f"{self.base_url}/memory/recommendations/{patron_id}",
            params=params
        )
        response.raise_for_status()
        return response.json()["recommendations"]


# Usage in agent
class FrontDeskAgent:
    def __init__(self):
        self.memory = MemoryClient()
        # ... other clients

    async def chat(self, message: str, patron_id: str):
        # Get profile
        profile = await self.memory.get_profile(patron_id)

        # If patron wants recommendations
        if "recommend" in message.lower():
            recommendations = await self.memory.get_recommendations(
                patron_id,
                context=message
            )
            # Format and return

        # Continue with conversation...
```

### Pros & Cons

**Pros:**
- ✅ **Simple and proven** - Standard REST patterns everyone knows
- ✅ **Easy to test** - Can use curl, Postman, standard HTTP testing
- ✅ **Clear boundaries** - Memory is obviously separate from agents
- ✅ **Independent deployment** - Can update memory service without touching agents
- ✅ **Standard observability** - HTTP metrics, logging, tracing

**Cons:**
- ❌ **Static contract** - Agents need to know API ahead of time
- ❌ **Less "AI-native"** - Doesn't feel integrated with agent tools
- ❌ **Manual caching** - Agent must implement caching logic
- ❌ **Synchronous** - HTTP calls add latency to agent responses

### When to Use

- **If**: You want simplicity and proven patterns
- **If**: You need independent service deployment
- **If**: Your team is more familiar with REST than MCP
- **If**: You want clear separation of concerns

---

## Option 3: Memory as Context Pre-Loader

### Concept

Memory service enriches agent context **before** the conversation starts, rather than being called during conversation.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CHAT SESSION START                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│              MEMORY PRE-LOADER (Middleware)                  │
│                                                              │
│  1. Fetch patron profile                                     │
│  2. Search relevant past sessions                            │
│  3. Build enriched context                                   │
│  4. Inject into agent system prompt                          │
│                                                              │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼ (enriched context)
┌─────────────────────────────────────────────────────────────┐
│                   FRONT DESK AGENT                           │
│                                                              │
│  System Prompt:                                              │
│  "You are the Front Desk Librarian...                        │
│                                                              │
│   ## PATRON CONTEXT (do not mention explicitly)             │
│   - This patron prefers tragedies and histories              │
│   - Last visit: asked about Border Wars primary sources      │
│   - Currently has 2 books checked out                        │
│   - Reading goal: complete all Stratum I tragedies           │
│                                                              │
│   Use this context naturally but don't reference it          │
│   explicitly unless relevant."                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
# agents/src/agents/context_enrichment.py

from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class EnrichedContext:
    """Context enriched with memory."""
    patron_profile: Dict
    recent_interactions: List[Dict]
    current_checkouts: List[Dict]
    system_prompt_addition: str


class MemoryContextEnricher:
    """Enriches agent context with memory before conversation."""

    def __init__(self, memory_store, circulation_client):
        self.memory = memory_store
        self.circulation = circulation_client

    async def enrich_context(
        self,
        patron_id: Optional[str],
        current_message: str
    ) -> EnrichedContext:
        """Load and structure context from memory."""

        if not patron_id:
            return EnrichedContext(
                patron_profile={},
                recent_interactions=[],
                current_checkouts=[],
                system_prompt_addition=""
            )

        # Load profile
        profile = await self.memory.get_semantic_memory(patron_id)

        if not profile or not profile.get("consent", {}).get("personalization"):
            # Patron hasn't consented to personalization
            return EnrichedContext(
                patron_profile=profile or {},
                recent_interactions=[],
                current_checkouts=[],
                system_prompt_addition=""
            )

        # Search relevant memories
        # (Use embedding of current message to find relevant past interactions)
        relevant_memories = await self.memory.search_episodic_memories(
            patron_id=patron_id,
            query_embedding=await self.embed(current_message),
            limit=3
        )

        # Get current checkouts
        checkouts = await self.circulation.get_patron_checkouts(patron_id)

        # Build system prompt addition
        prompt_addition = self._build_system_prompt_addition(
            profile,
            relevant_memories,
            checkouts
        )

        return EnrichedContext(
            patron_profile=profile,
            recent_interactions=relevant_memories,
            current_checkouts=checkouts,
            system_prompt_addition=prompt_addition
        )

    def _build_system_prompt_addition(
        self,
        profile: Dict,
        memories: List[Dict],
        checkouts: List[Dict]
    ) -> str:
        """Build the context addition to system prompt."""

        lines = ["\n## PATRON CONTEXT (use naturally, don't mention explicitly)"]

        # Preferences
        inferred = profile.get("inferred_preferences", {})
        if inferred.get("genres"):
            top_genres = inferred["genres"][:3]
            genres_str = ", ".join([g["genre"] for g in top_genres])
            lines.append(f"- This patron often reads: {genres_str}")

        explicit = profile.get("explicit_preferences", {})
        if explicit.get("reading_goals"):
            goal = explicit["reading_goals"]
            lines.append(f"- Reading goal: {goal.get('target', 'N/A')}")

        # Recent relevant interactions
        if memories:
            lines.append("- Recent relevant interactions:")
            for mem in memories[:2]:
                lines.append(f"  * {mem['summary']}")

        # Current checkouts
        if checkouts:
            lines.append(f"- Currently has {len(checkouts)} book(s) checked out")

        lines.append("\nUse this context to be helpful, but respond naturally.")

        return "\n".join(lines)


# Integration with ChatSession
class ChatSession:
    def __init__(self, patron_id: Optional[str] = None):
        self.patron_id = patron_id
        self.enricher = MemoryContextEnricher(memory_store, circulation_client)
        self.agent = FrontDeskAgent()

    async def send_message(self, message: str) -> str:
        """Send message with enriched context."""

        # Enrich context BEFORE agent processes message
        enriched = await self.enricher.enrich_context(
            self.patron_id,
            message
        )

        # Pass enriched context to agent
        # Agent sees this in its system prompt
        response = await self.agent.chat(
            message,
            system_prompt_addition=enriched.system_prompt_addition
        )

        return response
```

### Pros & Cons

**Pros:**
- ✅ **Simple agent logic** - Agent doesn't need to know about memory
- ✅ **Fast conversation** - No mid-conversation memory calls
- ✅ **Transparent** - Memory is invisible to agent reasoning
- ✅ **Easy caching** - Pre-load once per session

**Cons:**
- ❌ **Static per session** - Can't query memory mid-conversation
- ❌ **Over-fetching** - Loads memory even if not needed
- ❌ **Less dynamic** - Can't adapt memory queries based on conversation flow
- ❌ **Agent can't write memory** - Need separate post-conversation step

### When to Use

- **If**: You want simplest agent implementation
- **If**: Conversations are short and context doesn't change much
- **If**: You want to minimize agent complexity
- **If**: Pre-loading memory is fast enough

---

## Option 4: Event-Driven Memory

### Concept

Agents emit events (patron searched, book checked out) that memory service listens to. Memory updates asynchronously.

### Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   FRONT DESK AGENT                        │
│                                                           │
│  During conversation:                                     │
│  - Reads memory (HTTP or MCP)                             │
│  - Emits events (Pub/Sub)                                 │
│                                                           │
└────────────┬─────────────────────────────────────────────┘
             │
             │ Events:
             │ - patron.searched
             │ - book.checked_out
             │ - session.ended
             │
             ▼
    ┌────────────────────┐
    │   Pub/Sub Topic    │
    │   "agent-events"   │
    └────────┬───────────┘
             │
             │ (async)
             │
             ▼
┌──────────────────────────────────────────────────────────┐
│              MEMORY EVENT PROCESSOR                       │
│                                                           │
│  Listens for events:                                      │
│  - patron.searched → Update search preferences            │
│  - book.checked_out → Update genre preferences            │
│  - session.ended → Compress and store episodic memory     │
│                                                           │
│  Updates memory asynchronously                            │
│                                                           │
└──────────────────────────────────────────────────────────┘
```

### Event Schema

```python
# shared/src/shared/events.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class EventType(str, Enum):
    PATRON_SEARCHED = "patron.searched"
    BOOK_CHECKED_OUT = "book.checked_out"
    BOOK_RETURNED = "book.returned"
    HOLD_PLACED = "hold.placed"
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    RECOMMENDATION_REQUESTED = "recommendation.requested"


@dataclass
class AgentEvent:
    """Base event emitted by agents."""
    event_id: str
    event_type: EventType
    timestamp: datetime
    patron_id: str
    session_id: str
    data: dict


# Specific events
@dataclass
class PatronSearchedEvent(AgentEvent):
    """Emitted when patron searches for books."""
    event_type: EventType = EventType.PATRON_SEARCHED

    @property
    def search_query(self) -> str:
        return self.data["query"]

    @property
    def results_count(self) -> int:
        return self.data["results_count"]


@dataclass
class BookCheckedOutEvent(AgentEvent):
    """Emitted when book is checked out."""
    event_type: EventType = EventType.BOOK_CHECKED_OUT

    @property
    def book_id(self) -> str:
        return self.data["book_id"]

    @property
    def genres(self) -> List[str]:
        return self.data.get("genres", [])
```

### Agent Event Emission

```python
# agents/src/agents/event_emitter.py

from google.cloud import pubsub_v1
import json


class AgentEventEmitter:
    """Emit events to Pub/Sub for async processing."""

    def __init__(self, project_id: str, topic_name: str = "agent-events"):
        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(project_id, topic_name)

    async def emit(self, event: AgentEvent):
        """Emit an event."""
        message_data = json.dumps({
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp.isoformat(),
            "patron_id": event.patron_id,
            "session_id": event.session_id,
            "data": event.data
        }).encode("utf-8")

        future = self.publisher.publish(self.topic_path, message_data)
        await future.result()  # Wait for publish confirmation


# Usage in agent
class FrontDeskAgent:
    def __init__(self):
        self.events = AgentEventEmitter(project_id="your-project")

    async def chat(self, message: str, patron_id: str, session_id: str):
        # ... conversation logic ...

        # Emit event when patron searches
        if search_performed:
            await self.events.emit(PatronSearchedEvent(
                event_id=str(uuid4()),
                timestamp=datetime.utcnow(),
                patron_id=patron_id,
                session_id=session_id,
                data={
                    "query": search_query,
                    "results_count": len(results)
                }
            ))
```

### Memory Event Processor

```python
# services/memory/event_processor.py

from google.cloud import pubsub_v1
import json


class MemoryEventProcessor:
    """Process agent events to update memory asynchronously."""

    def __init__(self, memory_store):
        self.memory = memory_store
        self.subscriber = pubsub_v1.SubscriberClient()

    async def start(self, subscription_path: str):
        """Start listening for events."""

        def callback(message):
            event = json.loads(message.data)
            asyncio.create_task(self.process_event(event))
            message.ack()

        streaming_pull_future = self.subscriber.subscribe(
            subscription_path,
            callback=callback
        )

        await streaming_pull_future.result()

    async def process_event(self, event: dict):
        """Process a single event."""

        event_type = event["event_type"]
        patron_id = event["patron_id"]
        data = event["data"]

        if event_type == "patron.searched":
            await self._update_search_preferences(patron_id, data)

        elif event_type == "book.checked_out":
            await self._update_genre_preferences(patron_id, data)

        elif event_type == "session.ended":
            await self._compress_session(patron_id, data)

    async def _update_search_preferences(self, patron_id: str, data: dict):
        """Update preferences based on search behavior."""

        query = data["query"]

        # Extract genre/stratum from query
        # Update inferred preferences
        # This is async so doesn't block agent
        pass

    async def _update_genre_preferences(self, patron_id: str, data: dict):
        """Update genre preferences based on checkout."""

        genres = data.get("genres", [])

        # Increment evidence count for these genres
        profile = await self.memory.get_semantic_memory(patron_id)
        # ... update logic
        await self.memory.update_semantic_memory(patron_id, updates)
```

### Pros & Cons

**Pros:**
- ✅ **Decoupled** - Agents don't wait for memory updates
- ✅ **Scalable** - Can handle high event volume
- ✅ **Reliable** - Pub/Sub ensures delivery
- ✅ **Flexible** - Multiple consumers can process same events

**Cons:**
- ❌ **Eventually consistent** - Memory updates are delayed
- ❌ **Complex debugging** - Harder to trace event flow
- ❌ **Infrastructure overhead** - Need Pub/Sub setup
- ❌ **Read still needs sync** - Agent still needs to read memory synchronously

### When to Use

- **If**: You need high scalability
- **If**: You can tolerate eventual consistency
- **If**: You want to decouple memory writes from agent responses
- **If**: You have multiple services that need to react to agent actions

---

## Option 5: Hybrid ADK + MCP + A2A

### Concept

Use the right protocol for each use case:
- **ADK**: Agent orchestration and working memory
- **MCP**: Local memory queries (Hanno's own memory service)
- **A2A**: Cross-library memory queries (Hanno querying Mastodon's memory)

### Architecture

```
┌───────────────────────────────────────────────────────────────┐
│              HANNO MEMORIAL FRONT DESK AGENT (ADK)            │
│                                                               │
│  ADK Built-in State:                                          │
│  - Working memory (current session)                           │
│  - Conversation history                                       │
│  - Tool call history                                          │
│                                                               │
└─────┬──────────────────────┬──────────────────────┬─────────┘
      │                      │                      │
      │ MCP                  │ HTTP                 │ A2A
      │ (local memory)       │ (services)           │ (remote memory)
      │                      │                      │
      ▼                      ▼                      ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Memory MCP   │      │  Catalog     │      │  Mastodon    │
│ Server       │      │  Service     │      │  Library     │
│              │      │  :8001       │      │  Memory      │
│ - Episodic   │      │              │      │  (via A2A)   │
│ - Semantic   │      │              │      │              │
│ - Recommend  │      │              │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
      │
      ▼
┌──────────────┐
│  Firestore   │
│  (Storage)   │
└──────────────┘
```

### When Each Protocol Is Used

| Scenario | Protocol | Why |
|----------|----------|-----|
| Agent needs patron preferences | MCP | Local resource, dynamic discovery |
| Agent searches catalog | HTTP | Standard microservice call |
| Agent requests book from Mastodon | A2A | Cross-library protocol |
| Mastodon asks "What does patron prefer?" | A2A | But gets "access denied" - privacy boundary |
| Agent compresses session memory | MCP Tool | Memory-specific operation |
| Agent generates recommendations | MCP Tool | Complex reasoning over memory |

### Implementation

```python
# agents/src/agents/hybrid_memory_agent.py

from google.adk import Agent  # Hypothetical ADK import
from mcp.client import MCPClient
from a2a.client import A2AClient


class HybridMemoryAgent(Agent):
    """Agent using ADK + MCP + A2A for memory."""

    def __init__(self):
        super().__init__()

        # ADK handles working memory automatically
        # self.state is provided by ADK

        # MCP for local memory operations
        self.mcp_memory = MCPClient(server_url="mcp://memory")

        # A2A for cross-library queries
        self.a2a_client = A2AClient(library_id="hanno-memorial")

    async def process_message(self, message: str, patron_id: str):
        # ADK automatically manages conversation history (working memory)

        # Use MCP to query local memory
        patron_profile = await self.mcp_memory.read_resource(
            f"memory://patron/{patron_id}/profile"
        )

        # Agent reasons about the request
        if "recommend" in message.lower():
            # Use MCP tool for recommendations
            recommendations = await self.mcp_memory.call_tool(
                "get_recommendations",
                {"patron_id": patron_id, "context": message}
            )
            return self._format_recommendations(recommendations)

        if "find" in message.lower() and "another library" in message.lower():
            # Search other libraries via A2A
            # But DON'T share patron preferences via A2A (privacy boundary)
            results = await self._search_network(message)
            return self._format_network_results(results)

        # Normal conversation
        return await super().process_message(message)

    async def _search_network(self, query: str):
        """Search other libraries via A2A."""

        # Query Mastodon's catalog (OK)
        mastodon_holdings = await self.a2a_client.send_message(
            to_library="mastodon-institute",
            message_type="holdings_query",
            payload={"query": query}
        )

        # DO NOT query Mastodon's memory service
        # (That would violate privacy boundaries)

        return mastodon_holdings

    async def end_session(self, session_id: str, patron_id: str):
        """End session - ADK calls this automatically."""

        # ADK provides self.state with full conversation history
        conversation_history = self.state["messages"]

        # Use MCP to compress and store
        summary = await self.mcp_memory.call_tool(
            "store_interaction",
            {
                "patron_id": patron_id,
                "session_id": session_id,
                "conversation": conversation_history
            }
        )
```

### Pros & Cons

**Pros:**
- ✅ **Best of all worlds** - Use right tool for right job
- ✅ **Leverages ADK** - Don't reimplement what ADK provides
- ✅ **Clear boundaries** - Each protocol has specific purpose
- ✅ **Future-proof** - Can add new protocols as needed

**Cons:**
- ❌ **Most complex** - Three different protocols to manage
- ❌ **Cognitive load** - Developers must know which protocol to use when
- ❌ **Testing complexity** - Need to test all protocol interactions
- ❌ **Operational overhead** - Monitor three different systems

### When to Use

- **If**: You're fully committed to the Google ADK ecosystem
- **If**: You want to leverage ADK's built-in state management
- **If**: You need cross-library queries via A2A
- **If**: You value using the "right tool for the job"

---

## Comparison Matrix

| Criteria | MCP Server | HTTP Service | Context Pre-Loader | Event-Driven | Hybrid |
|----------|------------|--------------|-------------------|--------------|--------|
| **Implementation Complexity** | High | Low | Medium | High | Very High |
| **Agent Complexity** | Medium | Low | Very Low | Low | Medium |
| **Dynamic Discovery** | ✅ Yes | ❌ No | ❌ No | ❌ No | ✅ Yes |
| **Mid-Conversation Queries** | ✅ Yes | ✅ Yes | ❌ No | ⚠️ Read Only | ✅ Yes |
| **Latency** | Low | Medium | Very Low | Low (read), Async (write) | Low |
| **Scalability** | Medium | High | High | Very High | High |
| **Testability** | Medium | Very High | High | Medium | Low |
| **Failure Modes** | Cache/Degrade | Cache/Degrade | Proceed without | Queue events | Complex |
| **Cross-Library (A2A)** | ⚠️ Needs extension | ⚠️ Needs extension | ⚠️ Needs extension | ⚠️ Needs extension | ✅ Native |
| **Recommendation Engine** | ✅ As tool | ✅ As endpoint | ⚠️ Pre-computed | ⚠️ Async only | ✅ As tool |

---

## Recommendation Engine Integration

Regardless of the protocol choice, the recommendation engine can be implemented similarly:

### Recommendation Service

```python
# services/memory/recommender.py

from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Recommendation:
    """A book recommendation with explanation."""
    book_id: str
    title: str
    author: str
    genres: List[str]
    stratum: int
    confidence: float  # 0.0 to 1.0
    explanation: str


class RecommendationEngine:
    """Generate personalized book recommendations."""

    def __init__(self, catalog_service, memory_store, llm_client):
        self.catalog = catalog_service
        self.memory = memory_store
        self.llm = llm_client

    async def generate_recommendations(
        self,
        patron_id: str,
        context: Optional[str] = None,
        count: int = 5
    ) -> List[Recommendation]:
        """Generate recommendations for a patron."""

        # 1. Get patron profile
        profile = await self.memory.get_semantic_memory(patron_id)

        if not profile:
            # New patron - use popular books
            return await self._get_popular_books(count)

        # 2. Extract preferences
        inferred = profile.get("inferred_preferences", {})
        explicit = profile.get("explicit_preferences", {})

        # 3. Build candidate pool
        candidates = await self._build_candidate_pool(inferred, explicit, context)

        # 4. Score and rank
        scored = await self._score_candidates(patron_id, candidates, profile, context)

        # 5. Generate explanations
        recommendations = await self._explain_recommendations(
            scored[:count],
            profile,
            context
        )

        return recommendations

    async def _build_candidate_pool(
        self,
        inferred: Dict,
        explicit: Dict,
        context: Optional[str]
    ) -> List[Dict]:
        """Build pool of candidate books."""

        candidates = []

        # From explicit favorites
        if explicit.get("favorite_genres"):
            for genre in explicit["favorite_genres"]:
                books = await self.catalog.search_books(genre=genre, limit=20)
                candidates.extend(books)

        # From inferred preferences
        if inferred.get("genres"):
            for genre_pref in inferred["genres"][:3]:
                books = await self.catalog.search_books(
                    genre=genre_pref["genre"],
                    limit=15
                )
                candidates.extend(books)

        # From inferred strata
        if inferred.get("strata"):
            for stratum_pref in inferred["strata"][:2]:
                books = await self.catalog.search_books(
                    stratum=stratum_pref["stratum"],
                    limit=15
                )
                candidates.extend(books)

        # Context-based (if patron mentioned something specific)
        if context:
            contextual = await self.catalog.search_books(query=context, limit=10)
            candidates.extend(contextual)

        # Deduplicate
        unique_candidates = {book["id"]: book for book in candidates}
        return list(unique_candidates.values())

    async def _score_candidates(
        self,
        patron_id: str,
        candidates: List[Dict],
        profile: Dict,
        context: Optional[str]
    ) -> List[Dict]:
        """Score candidates based on patron preferences."""

        inferred = profile.get("inferred_preferences", {})
        explicit = profile.get("explicit_preferences", {})

        # Get books patron already has/read
        checkouts = await self.get_patron_reading_history(patron_id)
        read_book_ids = set(checkouts)

        scored = []

        for book in candidates:
            # Skip if already read
            if book["id"] in read_book_ids:
                continue

            score = 0.0

            # Genre match
            book_genres = set(book.get("genres", []))
            for genre_pref in inferred.get("genres", []):
                if genre_pref["genre"] in book_genres:
                    score += genre_pref["confidence"] * 0.4

            # Stratum match
            book_stratum = book.get("stratum")
            for stratum_pref in inferred.get("strata", []):
                if stratum_pref["stratum"] == book_stratum:
                    score += stratum_pref["confidence"] * 0.3

            # Author match
            book_author = book.get("author")
            for author_pref in inferred.get("authors", []):
                if author_pref["author"] == book_author:
                    score += author_pref["confidence"] * 0.3

            # Explicit favorites boost
            if book_author in explicit.get("favorite_authors", []):
                score += 0.5

            # Avoid list penalty
            if book_genres & set(explicit.get("avoid_genres", [])):
                score -= 0.5

            scored.append({**book, "score": max(0, score)})

        # Sort by score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    async def _explain_recommendations(
        self,
        scored_books: List[Dict],
        profile: Dict,
        context: Optional[str]
    ) -> List[Recommendation]:
        """Generate explanations for why books were recommended."""

        recommendations = []

        for book in scored_books:
            # Use LLM to generate natural explanation
            explanation_prompt = f"""Given this patron profile:
- Favorite genres: {profile.get('explicit_preferences', {}).get('favorite_genres', [])}
- Often reads: {[g['genre'] for g in profile.get('inferred_preferences', {}).get('genres', [])[:3]]}

Why would we recommend this book?
- Title: {book['title']}
- Author: {book['author']}
- Genres: {book['genres']}
- Stratum: {book['stratum']}

Generate a 1-sentence explanation."""

            explanation = await self.llm.generate(explanation_prompt)

            recommendations.append(Recommendation(
                book_id=book["id"],
                title=book["title"],
                author=book["author"],
                genres=book["genres"],
                stratum=book["stratum"],
                confidence=book["score"],
                explanation=explanation
            ))

        return recommendations
```

### How Agents Access Recommendations

Depends on the architecture choice:

**MCP Server:**
```python
recommendations = await mcp_client.call_tool(
    "get_recommendations",
    {"patron_id": patron_id, "context": message, "count": 5}
)
```

**HTTP Service:**
```python
response = await httpx.get(
    f"{memory_url}/memory/recommendations/{patron_id}",
    params={"context": message, "count": 5}
)
recommendations = response.json()["recommendations"]
```

**Context Pre-Loader:**
```python
# Recommendations pre-loaded in system prompt
# Agent mentions them naturally:
# "Based on your preferences, you might enjoy 'The Siege of Tuskmere'..."
```

---

## Evaluation Criteria

How do we decide which architecture to use? Test with evaluation scenarios:

### Scenario 1: Recommendation Accuracy

**Metric**: Do recommendations match stated preferences?

```python
class RecommendationAccuracyScenario:
    """Test if recommendations align with patron preferences."""

    async def execute(self, agent, architecture_type):
        # Set up patron with clear preferences
        patron = test_profiles["test-scholar-001"]  # Prefers tragedies

        # Ask for recommendations
        response = await agent.chat(
            "Can you recommend some books?",
            patron_id=patron["patron_id"]
        )

        # Extract recommended books from response
        recommended_books = self.extract_book_ids(response)

        # Check if recommendations match preferences
        tragedy_count = 0
        for book_id in recommended_books:
            book = await catalog.get_book(book_id)
            if "tragedy" in book["genres"] or book["stratum"] == 1:
                tragedy_count += 1

        accuracy = tragedy_count / len(recommended_books)

        return {
            "architecture": architecture_type,
            "accuracy": accuracy,
            "passed": accuracy >= 0.6  # At least 60% match
        }
```

### Scenario 2: Latency Under Load

**Metric**: Response time with 100 concurrent agents

```python
class MemoryLatencyScenario:
    """Test response time under load."""

    async def execute(self, architecture_type):
        agents = [create_agent(architecture_type) for _ in range(100)]

        start = time.time()

        # All agents ask for recommendations simultaneously
        tasks = [
            agent.chat("Recommend books", patron_id=f"patron-{i}")
            for i, agent in enumerate(agents)
        ]

        await asyncio.gather(*tasks)

        duration = time.time() - start

        return {
            "architecture": architecture_type,
            "total_duration_seconds": duration,
            "avg_response_time": duration / 100,
            "passed": duration < 30  # All complete in <30s
        }
```

### Scenario 3: Failure Recovery

**Metric**: Does agent degrade gracefully when memory service is down?

```python
class MemoryFailureScenario:
    """Test behavior when memory service fails."""

    async def execute(self, agent, architecture_type):
        # Start with memory service up
        response1 = await agent.chat(
            "Recommend books",
            patron_id="patron-001"
        )

        # Take down memory service
        async with chaos.inject_fault("memory", FaultType.OFFLINE):
            response2 = await agent.chat(
                "Recommend books",
                patron_id="patron-001"
            )

        # Check if agent:
        # 1. Still responded (didn't crash)
        # 2. Acknowledged limitation
        # 3. Offered generic help

        criteria = {
            "did_not_crash": response2 is not None,
            "acknowledged_limitation": any(
                phrase in response2.lower()
                for phrase in ["having trouble", "temporarily", "can't access"]
            ),
            "provided_fallback": len(response2) > 50  # Some helpful response
        }

        return {
            "architecture": architecture_type,
            "criteria": criteria,
            "passed": all(criteria.values())
        }
```

---

## Implementation Strategy

### Recommended Phased Approach

#### Phase 1: Start Simple (Weeks 1-4)

**Choice**: **HTTP Microservice** (Option 2)

**Why**:
- Proven patterns
- Easy to test
- Clear separation
- Can iterate quickly

**Deliverables**:
- Memory service at :8004 with REST API
- Basic HTTP client in agents
- Pre-made test profiles loaded
- Simple recommendation endpoint

#### Phase 2: Add MCP (Weeks 5-8)

**Choice**: **Add MCP Server** (Option 1) alongside HTTP

**Why**:
- Agents can discover memory capabilities
- Compare MCP vs HTTP in evaluation
- Learn MCP patterns

**Deliverables**:
- MCP server exposing memory as resources
- Agents can choose HTTP or MCP
- Evaluation comparing both approaches

#### Phase 3: Optimize (Weeks 9-12)

**Choice**: **Hybrid** (Option 5) or **Event-Driven** (Option 4)

**Why**:
- Data from Phase 1 & 2 shows which patterns work
- Can add event-driven writes while keeping sync reads
- Integrate with ADK more deeply

**Deliverables**:
- Event emission for async preference updates
- ADK integration for working memory
- A2A integration for cross-library queries

### Decision Tree

```
Start
  │
  ├─> Need simplicity? → HTTP Service (Option 2)
  │
  ├─> Want future-proof? → MCP Server (Option 1)
  │
  ├─> Agent complexity must be minimal? → Context Pre-Loader (Option 3)
  │
  ├─> Need massive scale? → Event-Driven (Option 4)
  │
  └─> All-in on ADK + MCP + A2A? → Hybrid (Option 5)
```

---

## Conclusion

**There is no single "right" answer** - this is a research question to be validated through implementation and evaluation.

### Recommendation for Your Project

**Start with Option 2 (HTTP Microservice)** because:
1. ✅ You can implement it in 1-2 weeks
2. ✅ It's testable with standard tools
3. ✅ It clearly demonstrates the "microservice architecture" thesis
4. ✅ It doesn't commit you to a specific pattern
5. ✅ You can add MCP/events/ADK later

**Then evolve to Option 5 (Hybrid)** as you learn:
1. Phase 1: HTTP for everything
2. Phase 2: Add MCP when you see benefits
3. Phase 3: Add events when you need async
4. Phase 4: Integrate ADK when you understand its strengths

### What to Document

Create test scenarios that compare architectures:
- **Recommendation accuracy** (do they all produce good recommendations?)
- **Latency** (which is fastest under load?)
- **Failure recovery** (which degrades most gracefully?)
- **Developer experience** (which is easiest to work with?)
- **Agent reasoning quality** (does architecture affect agent behavior?)

The evaluation results will tell you which architecture works best for "Can an AI run a library?"

---

**Document Version**: 1.0
**Status**: Architecture Exploration
**Next Steps**: Implement Option 2, evaluate, iterate
