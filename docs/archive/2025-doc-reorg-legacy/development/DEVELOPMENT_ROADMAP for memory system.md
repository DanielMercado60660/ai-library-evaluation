# Memory System Development Roadmap

**Version:** 1.0
**Last Updated:** 2026-02-02
**Status:** Planning Phase

## Executive Summary

This document outlines the development approach for integrating the Memory System into the AI Library evaluation platform. The development follows an **interface-driven, test-first, iterative methodology** that aligns with the project's core thesis: "Can an AI run a library?"

**Core Principle:** Build incrementally, test systematically, evolve architecturally.

---

## 1. Development Philosophy

### 1.1 Object-Oriented Design (OOP)

All components are designed around **interfaces** that define contracts without coupling to specific implementations. This enables:

- **Swappable implementations**: Change storage backends (in-memory → Firestore → Cloud SQL) without touching agent code
- **Independent testing**: Mock interfaces for unit tests, use real implementations for integration tests
- **Incremental enhancement**: Add new transports (HTTP → FastMCP → gRPC) without breaking existing functionality
- **Model agnosticism**: Memory system works identically regardless of LLM provider (Gemini, Claude, GPT-4)

### 1.2 Test-Driven Development (TDD)

Every feature begins with a failing test. Tests are organized in three layers:

1. **Unit Tests** (`tests/unit/`): Test individual components in isolation using mocks
2. **Integration Tests** (`tests/integration/`): Test component interactions with real dependencies
3. **Evaluation Scenarios** (`tests/evaluation/`): Test end-to-end library automation capabilities

**TDD Workflow:**
```
Write Test → Run (should fail) → Implement Feature → Run (should pass) → Refactor → Repeat
```

### 1.3 Iterative Architecture Evolution

The memory system evolves through three phases, each building on the previous:

| Phase | Storage | Transport | Timeline | Purpose |
|-------|---------|-----------|----------|---------|
| **Phase 1: Foundation** | In-Memory → Firestore | HTTP REST | Weeks 1-4 | Prove architecture, establish patterns |
| **Phase 2: Enhancement** | Firestore (production) | HTTP + FastMCP | Weeks 5-8 | Add local resource access, improve performance |
| **Phase 3: Enterprise** | Cloud SQL (optional) | HTTP + FastMCP + gRPC | Weeks 9-12 | Scale to multi-library A2A communication |

---

## 2. Interface Hierarchy

### 2.1 Core Interfaces

```python
# memory/interfaces.py

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime

class IMemoryStore(ABC):
    """Storage backend interface - swap implementations without changing logic."""

    @abstractmethod
    async def save_interaction(
        self,
        patron_id: str,
        message: str,
        response: str,
        timestamp: datetime
    ) -> str:
        """Save an interaction to episodic memory. Returns interaction_id."""
        pass

    @abstractmethod
    async def get_recent_interactions(
        self,
        patron_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """Retrieve recent interactions for working memory."""
        pass

    @abstractmethod
    async def search_interactions(
        self,
        patron_id: str,
        query_embedding: List[float],
        limit: int = 5
    ) -> List[Dict]:
        """Semantic search through episodic memory."""
        pass

    @abstractmethod
    async def get_profile(self, patron_id: str) -> Optional[Dict]:
        """Retrieve semantic memory (long-term profile)."""
        pass

    @abstractmethod
    async def update_profile(self, patron_id: str, updates: Dict) -> None:
        """Update semantic memory profile."""
        pass


class IMemoryService(ABC):
    """Business logic interface - orchestrates storage and embeddings."""

    @abstractmethod
    async def recall_context(
        self,
        patron_id: str,
        current_message: str
    ) -> Dict:
        """Retrieve relevant memory context for current conversation."""
        pass

    @abstractmethod
    async def recommend_books(
        self,
        patron_id: str,
        context: str
    ) -> List[Dict]:
        """Generate personalized recommendations based on memory."""
        pass

    @abstractmethod
    async def record_interaction(
        self,
        patron_id: str,
        message: str,
        response: str
    ) -> None:
        """Record a completed interaction across all memory tiers."""
        pass


class IMemoryTransport(ABC):
    """Communication interface - how agents access memory."""

    @abstractmethod
    async def recall(self, patron_id: str, query: str) -> Dict:
        """Recall memory context via transport protocol."""
        pass

    @abstractmethod
    async def recommend(self, patron_id: str, context: str) -> List[Dict]:
        """Get recommendations via transport protocol."""
        pass

    @abstractmethod
    async def record(self, patron_id: str, message: str, response: str) -> None:
        """Record interaction via transport protocol."""
        pass
```

### 2.2 Interface Benefits

- **IMemoryStore**: Test with `InMemoryStore` (fast, deterministic), deploy with `FirestoreStore` (persistent, scalable)
- **IMemoryService**: Mock for agent tests, use real service for integration tests
- **IMemoryTransport**: Start with `HTTPTransport`, add `MCPTransport`, upgrade to `gRPCTransport`

---

## 3. Phase 1: Foundation (Weeks 1-4)

**Goal:** Establish working memory system with HTTP access and Firestore storage.

### 3.1 Week 1: Interfaces + In-Memory Implementation

**Deliverables:**
- `memory/interfaces.py` - Core interface definitions
- `memory/stores/in_memory.py` - Simple in-memory implementation
- `memory/services/memory_service.py` - Business logic implementation
- `tests/unit/test_memory_store.py` - Unit tests for store interface

**Test-First Example:**
```python
# tests/unit/test_memory_store.py

import pytest
from memory.interfaces import IMemoryStore
from memory.stores.in_memory import InMemoryStore

@pytest.fixture
def store() -> IMemoryStore:
    return InMemoryStore()

@pytest.mark.asyncio
async def test_save_and_retrieve_interaction(store):
    # Arrange
    patron_id = "test_patron_001"
    message = "Do you have any books by Maren Greyhorn?"
    response = "Yes, I found several titles..."

    # Act
    interaction_id = await store.save_interaction(
        patron_id, message, response, datetime.utcnow()
    )
    interactions = await store.get_recent_interactions(patron_id, limit=1)

    # Assert
    assert interaction_id is not None
    assert len(interactions) == 1
    assert interactions[0]["message"] == message
    assert interactions[0]["response"] == response
```

**Week 1 Test Coverage:**
- ✅ Save interaction
- ✅ Retrieve recent interactions
- ✅ Profile CRUD operations
- ✅ Interaction ordering (most recent first)

---

### 3.2 Week 2: Firestore + Embeddings

**Deliverables:**
- `memory/stores/firestore.py` - Firestore implementation of IMemoryStore
- `memory/embeddings/vertex_ai.py` - Vertex AI embedding service
- `memory/services/memory_service.py` - Updated with semantic search
- `tests/integration/test_firestore_store.py` - Integration tests

**Test-First Example:**
```python
# tests/integration/test_firestore_store.py

import pytest
from memory.stores.firestore import FirestoreStore
from memory.embeddings.vertex_ai import VertexAIEmbeddings

@pytest.fixture
def store() -> FirestoreStore:
    return FirestoreStore(project_id="ai-library-eval-dev")

@pytest.fixture
def embeddings() -> VertexAIEmbeddings:
    return VertexAIEmbeddings(model="textembedding-gecko@003")

@pytest.mark.asyncio
async def test_semantic_search(store, embeddings):
    # Arrange: Save three interactions
    patron_id = "test_patron_002"
    interactions = [
        ("I love tragic poetry", "Have you read Maren Greyhorn?"),
        ("Do you have children's books?", "Yes, we have Penelope Trunkling..."),
        ("What about epic tragedies?", "Our Stratum I section has many...")
    ]

    for msg, resp in interactions:
        embedding = await embeddings.embed(msg)
        await store.save_interaction(
            patron_id, msg, resp, datetime.utcnow(), embedding
        )

    # Act: Search for tragedy-related content
    query_embedding = await embeddings.embed("tragic plays")
    results = await store.search_interactions(
        patron_id, query_embedding, limit=2
    )

    # Assert: Should return tragedy interactions, not children's books
    assert len(results) == 2
    assert "tragic" in results[0]["message"].lower() or "tragedies" in results[0]["message"].lower()
    assert "children" not in results[0]["message"].lower()
```

**Week 2 Test Coverage:**
- ✅ Firestore CRUD operations
- ✅ Vertex AI embedding generation
- ✅ Semantic search with vector similarity
- ✅ Embedding storage and retrieval

---

### 3.3 Week 3: HTTP Transport + Memory Service

**Deliverables:**
- `services/memory/app.py` - FastAPI memory service (:8004)
- `memory/transports/http.py` - HTTP client implementation of IMemoryTransport
- `tests/integration/test_http_transport.py` - API endpoint tests
- OpenAPI documentation at `/docs`

**API Specification:**
```yaml
# services/memory/openapi.yaml

paths:
  /api/v1/memory/recall:
    post:
      summary: Recall memory context for current conversation
      parameters:
        - name: patron_id
          in: body
          required: true
          schema: {type: string}
        - name: query
          in: body
          required: true
          schema: {type: string}
      responses:
        200:
          description: Memory context retrieved
          schema:
            type: object
            properties:
              working_memory: {type: array}
              episodic_memory: {type: array}
              semantic_memory: {type: object}

  /api/v1/memory/recommend:
    post:
      summary: Get personalized book recommendations
      parameters:
        - name: patron_id
          in: body
          required: true
        - name: context
          in: body
          required: true
      responses:
        200:
          description: Recommendations generated
          schema:
            type: array
            items:
              type: object
              properties:
                book_id: {type: string}
                title: {type: string}
                confidence: {type: number}
                reason: {type: string}
```

**Test-First Example:**
```python
# tests/integration/test_http_transport.py

import pytest
import httpx
from memory.transports.http import HTTPMemoryTransport

@pytest.fixture
def transport() -> HTTPMemoryTransport:
    return HTTPMemoryTransport(base_url="http://localhost:8004")

@pytest.mark.asyncio
async def test_recall_context_via_http(transport):
    # Arrange
    patron_id = "test_patron_003"
    query = "What books did I like last time?"

    # Act
    context = await transport.recall(patron_id, query)

    # Assert
    assert "working_memory" in context
    assert "episodic_memory" in context
    assert "semantic_memory" in context
    assert isinstance(context["working_memory"], list)
```

**Week 3 Test Coverage:**
- ✅ POST /api/v1/memory/recall
- ✅ POST /api/v1/memory/recommend
- ✅ POST /api/v1/memory/record
- ✅ Error handling (404, 500)
- ✅ Transport retry logic

---

### 3.4 Week 4: Agent Integration + Pre-Made Profiles

**Deliverables:**
- `agents/memory_aware_agent.py` - FrontDeskAgent with memory integration
- `memory/profiles/bootstrap.py` - Pre-made test profiles
- `tests/integration/test_memory_aware_agent.py` - End-to-end tests
- `tests/evaluation/scenarios/memory/` - Memory-specific evaluation scenarios

**Pre-Made Test Profiles:**
```python
# memory/profiles/bootstrap.py

BOOTSTRAP_PROFILES = {
    "scholar_001": {
        "profile_level": "personalized",
        "preferences": {
            "favorite_genres": ["tragedy", "philosophy", "history"],
            "favorite_authors": ["Maren Greyhorn", "Dr. H. Caladent"],
            "reading_pace": "slow_deep",
            "typical_loan_period": 21,
        },
        "consent": {"recommendation_engine": True, "long_term_memory": True},
        "past_interactions": [
            {"message": "I'm looking for verse tragedies", "books_found": ["TTT001", "TTT002"]},
            {"message": "Do you have anything by Maren Greyhorn?", "books_found": ["TTT001", "TTT003"]},
        ]
    },
    "browser_002": {
        "profile_level": "registered",
        "preferences": {"favorite_genres": ["fiction"]},
        "consent": {"recommendation_engine": False, "long_term_memory": False},
        "past_interactions": []
    },
    # ... parent_003, new_user_004
}

async def load_bootstrap_profiles(store: IMemoryStore):
    """Load pre-made profiles into memory system for testing."""
    for patron_id, data in BOOTSTRAP_PROFILES.items():
        await store.update_profile(patron_id, data["preferences"])
        for interaction in data.get("past_interactions", []):
            await store.save_interaction(
                patron_id,
                interaction["message"],
                f"Found books: {interaction['books_found']}",
                datetime.utcnow()
            )
```

**Agent Integration Test:**
```python
# tests/integration/test_memory_aware_agent.py

import pytest
from agents.memory_aware_agent import MemoryAwareFrontDeskAgent
from memory.transports.http import HTTPMemoryTransport

@pytest.fixture
def agent() -> MemoryAwareFrontDeskAgent:
    memory = HTTPMemoryTransport("http://localhost:8004")
    return MemoryAwareFrontDeskAgent(memory=memory)

@pytest.mark.asyncio
async def test_personalized_recommendation(agent):
    # Arrange: Use pre-made scholar profile
    patron_id = "scholar_001"
    message = "What would you recommend for me today?"

    # Act
    response = await agent.chat(message, patron_id=patron_id)

    # Assert: Should recommend based on profile preferences
    assert "tragedy" in response.lower() or "greyhorn" in response.lower()
    # Should use tools to search catalog
    assert agent.last_tool_calls  # Agent used catalog_search
    # Should NOT hallucinate
    assert "TTT" in response  # Real book ID from catalog
```

**Week 4 Test Coverage:**
- ✅ Agent recalls context before responding
- ✅ Recommendations use memory-based preferences
- ✅ Interactions recorded after completion
- ✅ Anonymous users work without memory
- ✅ Evaluation scenario: `MemoryPersonalizationScenario`

---

### 3.5 Phase 1 Milestone Criteria

**✅ Definition of Done:**
- [ ] All unit tests pass (>95% coverage)
- [ ] All integration tests pass
- [ ] Memory service runs on :8004
- [ ] FrontDeskAgent successfully retrieves memory context
- [ ] Pre-made profiles loaded and functional
- [ ] OpenAPI documentation complete
- [ ] At least 1 evaluation scenario passes (personalization)

**🎯 Architecture Validation:**
- Agents can swap between `InMemoryStore` and `FirestoreStore` without code changes
- Memory service can be mocked for agent unit tests
- HTTP transport can be replaced without touching agent logic

---

## 4. Phase 2: Enhancement (Weeks 5-8)

**Goal:** Add FastMCP transport for local resource access and improve performance.

### 4.1 Week 5-6: MCP Server Implementation

**Deliverables:**
- `services/memory/mcp_server.py` - FastMCP server exposing memory as resources
- `memory/transports/mcp.py` - MCP client implementation of IMemoryTransport
- `tests/integration/test_mcp_transport.py` - MCP protocol tests

**MCP Resource Definitions:**
```python
# services/memory/mcp_server.py

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AI Library Memory System")

@mcp.resource("memory://patron/{patron_id}/context")
async def get_patron_context(patron_id: str) -> str:
    """Retrieve memory context as MCP resource."""
    memory_service = get_memory_service()
    context = await memory_service.recall_context(patron_id, "")
    return json.dumps(context)

@mcp.tool()
async def recommend_books(patron_id: str, context: str) -> list[dict]:
    """Generate recommendations via MCP tool."""
    memory_service = get_memory_service()
    return await memory_service.recommend_books(patron_id, context)

@mcp.tool()
async def record_interaction(patron_id: str, message: str, response: str):
    """Record interaction via MCP tool."""
    memory_service = get_memory_service()
    await memory_service.record_interaction(patron_id, message, response)
```

**Test-First Example:**
```python
# tests/integration/test_mcp_transport.py

import pytest
from memory.transports.mcp import MCPMemoryTransport

@pytest.fixture
def transport() -> MCPMemoryTransport:
    return MCPMemoryTransport(server_url="mcp://memory")

@pytest.mark.asyncio
async def test_mcp_resource_discovery(transport):
    # Act
    resources = await transport.list_resources()

    # Assert
    assert any(r["uri"].startswith("memory://patron/") for r in resources)

@pytest.mark.asyncio
async def test_mcp_tool_invocation(transport):
    # Arrange
    patron_id = "scholar_001"
    context = "Looking for philosophical works"

    # Act
    recommendations = await transport.recommend(patron_id, context)

    # Assert
    assert len(recommendations) > 0
    assert all("book_id" in r for r in recommendations)
```

**Week 5-6 Test Coverage:**
- ✅ MCP server starts and exposes resources
- ✅ Resource URI patterns work (`memory://patron/{id}/context`)
- ✅ MCP tools callable from client
- ✅ Agent can use both HTTP and MCP transports interchangeably

---

### 4.2 Week 7-8: Performance Optimization + Caching

**Deliverables:**
- `memory/cache/redis.py` - Redis caching layer for embeddings
- `memory/services/batch_embeddings.py` - Batch embedding generation
- Performance benchmarks comparing HTTP vs MCP
- Load testing results (100 concurrent users)

**Optimization Test:**
```python
# tests/performance/test_memory_latency.py

import pytest
import time
from memory.transports.http import HTTPMemoryTransport
from memory.transports.mcp import MCPMemoryTransport

@pytest.mark.asyncio
async def test_latency_comparison():
    http = HTTPMemoryTransport("http://localhost:8004")
    mcp = MCPMemoryTransport("mcp://memory")

    patron_id = "scholar_001"
    query = "What books did I like?"

    # HTTP latency
    start = time.time()
    for _ in range(100):
        await http.recall(patron_id, query)
    http_time = time.time() - start

    # MCP latency
    start = time.time()
    for _ in range(100):
        await mcp.recall(patron_id, query)
    mcp_time = time.time() - start

    # Assert: MCP should be faster for local access
    print(f"HTTP: {http_time:.2f}s | MCP: {mcp_time:.2f}s")
    # Note: Actual assertion depends on setup, this is informational
```

**Week 7-8 Test Coverage:**
- ✅ Redis cache hit/miss tracking
- ✅ Embedding reuse (don't re-embed identical queries)
- ✅ Batch embedding performance >10x single calls
- ✅ Load test: 100 concurrent users with <500ms p95 latency

---

### 4.3 Phase 2 Milestone Criteria

**✅ Definition of Done:**
- [ ] FastMCP server operational
- [ ] Agents can use MCP transport
- [ ] Performance benchmarks documented
- [ ] Caching reduces embedding costs by >60%
- [ ] Evaluation scenario: `MCPResourceAccessScenario`

**🎯 Architecture Validation:**
- Agent code unchanged when switching HTTP → MCP
- MCP transport works both locally (dev) and remote (production)

---

## 5. Phase 3: Enterprise Scale (Weeks 9-12)

**Goal:** Add gRPC for A2A communication and optionally migrate to Cloud SQL.

### 5.1 Week 9-10: gRPC Transport

**Deliverables:**
- `services/memory/grpc_server.py` - gRPC service definition
- `memory/transports/grpc.py` - gRPC client implementation
- `protos/memory.proto` - Protocol buffer definitions
- Cross-library memory federation tests

**Protocol Buffer Definition:**
```protobuf
// protos/memory.proto

syntax = "proto3";

package memory;

service MemoryService {
  rpc RecallContext (RecallRequest) returns (RecallResponse);
  rpc RecommendBooks (RecommendRequest) returns (RecommendResponse);
  rpc RecordInteraction (RecordRequest) returns (RecordResponse);
}

message RecallRequest {
  string patron_id = 1;
  string query = 2;
}

message RecallResponse {
  repeated Interaction working_memory = 1;
  repeated Interaction episodic_memory = 2;
  Profile semantic_memory = 3;
}

message RecommendRequest {
  string patron_id = 1;
  string context = 2;
}

message RecommendResponse {
  repeated Recommendation recommendations = 1;
}
```

**Test-First Example:**
```python
# tests/integration/test_grpc_transport.py

import pytest
from memory.transports.grpc import gRPCMemoryTransport

@pytest.fixture
def transport() -> gRPCMemoryTransport:
    return gRPCMemoryTransport("memory.service.internal:50051")

@pytest.mark.asyncio
async def test_grpc_recall_performance(transport):
    # Arrange
    patron_id = "scholar_001"
    query = "Recent interactions"

    # Act
    start = time.time()
    for _ in range(1000):  # 1000 calls
        await transport.recall(patron_id, query)
    elapsed = time.time() - start

    # Assert: gRPC should handle 1000 calls in <5 seconds
    assert elapsed < 5.0
    print(f"gRPC: {1000/elapsed:.2f} QPS")
```

**Week 9-10 Test Coverage:**
- ✅ gRPC service starts and accepts connections
- ✅ Protocol buffer serialization/deserialization
- ✅ gRPC performance >10x HTTP for high-volume calls
- ✅ A2A scenario: Cross-library recommendation sharing

---

### 5.2 Week 11-12: Cloud SQL Migration (Optional)

**Deliverables:**
- `memory/stores/cloudsql.py` - Cloud SQL (PostgreSQL) implementation
- `migrations/` - Alembic database migrations
- Performance comparison: Firestore vs Cloud SQL
- Production deployment guide

**Migration Strategy:**
```python
# memory/stores/cloudsql.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from memory.interfaces import IMemoryStore

class CloudSQLStore(IMemoryStore):
    """PostgreSQL implementation with pgvector for embeddings."""

    def __init__(self, connection_string: str):
        self.engine = create_async_engine(connection_string)

    async def search_interactions(
        self,
        patron_id: str,
        query_embedding: List[float],
        limit: int = 5
    ) -> List[Dict]:
        """Use pgvector cosine similarity for semantic search."""
        async with AsyncSession(self.engine) as session:
            # Use pgvector's <-> operator for cosine distance
            query = """
                SELECT interaction_id, message, response,
                       embedding <-> :query_embedding AS distance
                FROM interactions
                WHERE patron_id = :patron_id
                ORDER BY distance ASC
                LIMIT :limit
            """
            result = await session.execute(
                query,
                {"patron_id": patron_id, "query_embedding": query_embedding, "limit": limit}
            )
            return [dict(row) for row in result]
```

**Week 11-12 Test Coverage:**
- ✅ Alembic migrations apply cleanly
- ✅ pgvector extension installed and working
- ✅ Cloud SQL semantic search matches Firestore results
- ✅ Data migration script (Firestore → Cloud SQL)

---

### 5.3 Phase 3 Milestone Criteria

**✅ Definition of Done:**
- [ ] gRPC transport functional
- [ ] Performance benchmarks show gRPC >10x HTTP
- [ ] (Optional) Cloud SQL migration complete
- [ ] A2A memory federation tested between two libraries
- [ ] Evaluation scenario: `A2AMemoryFederationScenario`

**🎯 Architecture Validation:**
- Agent can use HTTP, MCP, or gRPC without code changes
- Storage backend (Firestore or Cloud SQL) swappable via config
- Production-ready deployment on Google Cloud

---

## 6. Test Organization

```
tests/
├── unit/                           # Fast, isolated tests
│   ├── test_memory_store.py       # IMemoryStore implementations
│   ├── test_embeddings.py         # Vertex AI embedding service
│   └── test_cache.py              # Redis caching layer
│
├── integration/                    # Multi-component tests
│   ├── test_memory_service.py     # MemoryService with real store
│   ├── test_http_transport.py     # HTTP API endpoints
│   ├── test_mcp_transport.py      # MCP resource/tool access
│   ├── test_grpc_transport.py     # gRPC service calls
│   └── test_memory_aware_agent.py # Agent with memory integration
│
├── performance/                    # Load and latency tests
│   ├── test_memory_latency.py     # Response time benchmarks
│   ├── test_concurrent_users.py   # 100+ concurrent users
│   └── test_embedding_batch.py    # Batch vs single embedding
│
└── evaluation/                     # End-to-end evaluation scenarios
    └── scenarios/
        └── memory/
            ├── personalization.py  # MemoryPersonalizationScenario
            ├── mcp_access.py       # MCPResourceAccessScenario
            └── a2a_federation.py   # A2AMemoryFederationScenario
```

### 6.1 Running Tests

```bash
# Unit tests (fast, no external dependencies)
pytest tests/unit/ -v

# Integration tests (requires services running)
docker-compose up -d firestore redis
pytest tests/integration/ -v

# Performance tests (requires load generation)
pytest tests/performance/ -v --benchmark

# Evaluation scenarios (end-to-end)
pytest tests/evaluation/ -v --scenario=all
```

---

## 7. Integration with Existing Services

### 7.1 Service Ports

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Catalog | 8001 | HTTP | Book metadata and search |
| Circulation | 8002 | HTTP | Checkouts, returns, holds |
| Recommendation | 8003 | HTTP | *(deprecated - merged into Memory)* |
| **Memory** | **8004** | **HTTP/gRPC** | **User profiles and recommendations** |
| Auth | 8005 | HTTP | Patron authentication |

### 7.2 Agent Tool Hierarchy

```python
# agents/memory_aware_agent.py

class MemoryAwareFrontDeskAgent(FrontDeskAgent):
    def __init__(self, memory: IMemoryTransport):
        super().__init__()
        self.memory = memory  # Injected transport (HTTP, MCP, or gRPC)
        self._update_tools()

    def _update_tools(self):
        """Add memory-aware tools to existing catalog/circulation tools."""
        self.tools.extend([
            types.FunctionDeclaration(
                name="get_personalized_recommendations",
                description="Get book recommendations based on patron's reading history and preferences",
                parameters={
                    "type": "object",
                    "properties": {
                        "patron_id": {"type": "string"},
                        "context": {"type": "string", "description": "Current conversation context"}
                    },
                    "required": ["patron_id", "context"]
                }
            )
        ])

    async def chat(self, message: str, patron_id: Optional[str] = None) -> str:
        # Step 1: Retrieve memory context
        memory_context = None
        if patron_id:
            memory_context = await self.memory.recall(patron_id, message)

        # Step 2: Build enhanced system prompt
        system_prompt = self._build_memory_aware_prompt(memory_context)

        # Step 3: Continue with normal agent loop (tool calling, etc.)
        return await super().chat(message, system_instruction=system_prompt)
```

---

## 8. Technology Stack Alignment

### 8.1 Google Vertical Components

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **Agent Framework** | Google Agent Development Kit (ADK) | Advanced tool management, state persistence |
| **LLM** | Gemini 3.0 Flash | Starting point (existing credits), model-agnostic design |
| **Embeddings** | Vertex AI (textembedding-gecko@003) | Google-native, high quality, 768 dimensions |
| **Storage (Dev)** | Firestore | Document-based, real-time, easy setup |
| **Storage (Prod)** | Cloud SQL (PostgreSQL + pgvector) | Relational, pgvector for embeddings, production-grade |
| **Caching** | Redis (Cloud Memorystore) | Fast embedding cache, session storage |
| **Transport** | HTTP → FastMCP → gRPC | Incremental evolution: simple → local → enterprise |
| **Frontend** | Angular | Google alignment, component-based architecture |

### 8.2 Configuration Management

```python
# agents/src/agents/config.py

# Service URLs
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8001")
CIRCULATION_URL = os.getenv("CIRCULATION_URL", "http://localhost:8002")
MEMORY_URL = os.getenv("MEMORY_URL", "http://localhost:8004")  # NEW
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8005")

# Memory Configuration
MEMORY_TRANSPORT = os.getenv("MEMORY_TRANSPORT", "http")  # http | mcp | grpc
MEMORY_STORE = os.getenv("MEMORY_STORE", "firestore")  # in_memory | firestore | cloudsql

# Vertex AI
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "ai-library-eval")
VERTEX_EMBEDDING_MODEL = os.getenv("VERTEX_EMBEDDING_MODEL", "textembedding-gecko@003")

# LLM Configuration
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.0-flash")
AGENT_MAX_ITERATIONS = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
```

---

## 9. Pre-Made Profile Bootstrap Strategy

### 9.1 Four Test Profiles

| Profile ID | Level | Consent | Purpose |
|------------|-------|---------|---------|
| `scholar_001` | Personalized | Full | Test deep personalization, recommendation accuracy |
| `browser_002` | Registered | Minimal | Test opt-out behavior, anonymous browsing |
| `parent_003` | Active | Moderate | Test family preferences, children's books |
| `new_user_004` | Anonymous | None | Test cold-start problem, progressive profiling |

### 9.2 Bootstrap Loading

```python
# scripts/load_bootstrap_profiles.py

import asyncio
from memory.stores.firestore import FirestoreStore
from memory.profiles.bootstrap import BOOTSTRAP_PROFILES, load_bootstrap_profiles

async def main():
    store = FirestoreStore(project_id="ai-library-eval-dev")
    await load_bootstrap_profiles(store)
    print("✅ Loaded 4 bootstrap profiles")

if __name__ == "__main__":
    asyncio.run(main())
```

**Usage in Tests:**
```python
@pytest.fixture(scope="session", autouse=True)
async def bootstrap_test_data():
    """Load bootstrap profiles once per test session."""
    store = FirestoreStore(project_id="ai-library-eval-test")
    await load_bootstrap_profiles(store)
    yield
    # Teardown: clean up test data
```

---

## 10. Evaluation Approach

### 10.1 Memory-Specific Evaluation Scenarios

```python
# tests/evaluation/scenarios/memory/personalization.py

from evaluation.base_scenario import BaseScenario, ScenarioResult

class MemoryPersonalizationScenario(BaseScenario):
    """Test that memory system improves recommendation accuracy."""

    name = "Memory-Based Personalization"
    description = "Verify agent uses patron history to personalize recommendations"

    async def run(self, agent: MemoryAwareFrontDeskAgent) -> ScenarioResult:
        # Use scholar_001 profile (loves tragedies)
        patron_id = "scholar_001"

        # Step 1: Ask for recommendations
        response = await agent.chat(
            "What would you recommend for me?",
            patron_id=patron_id
        )

        # Step 2: Validate recommendations use profile
        checks = {
            "uses_memory": patron_id in agent.memory.last_recall_call,
            "recommends_tragedy": "tragedy" in response.lower() or "greyhorn" in response.lower(),
            "no_children_books": "penelope trunkling" not in response.lower(),
            "uses_catalog_tool": agent.last_tool_calls.get("catalog_search") is not None,
            "no_hallucination": any(book_id.startswith("TTT") for book_id in self._extract_book_ids(response))
        }

        return ScenarioResult(
            scenario_name=self.name,
            success=all(checks.values()),
            checks=checks,
            transcript=agent.conversation_history
        )
```

### 10.2 Evaluation Dimensions

| Dimension | Metric | Target |
|-----------|--------|--------|
| **Personalization Accuracy** | % recommendations matching profile | >80% |
| **Cold Start Handling** | Success rate for anonymous users | >95% |
| **Memory Recall Latency** | p95 latency for context retrieval | <200ms |
| **Hallucination Prevention** | % responses with only real books | >99% |
| **Tool Usage Efficiency** | Avg tools called per request | <3 |
| **Privacy Compliance** | % consent violations | 0% |

---

## 11. Week-by-Week Deliverable Timeline

### Phase 1: Foundation (Weeks 1-4)

| Week | Deliverable | Tests | Milestone |
|------|-------------|-------|-----------|
| **1** | Interfaces + InMemoryStore | Unit tests (store, service) | ✅ Interfaces established |
| **2** | FirestoreStore + Embeddings | Integration tests (Firestore, Vertex AI) | ✅ Persistent storage working |
| **3** | HTTP Transport + FastAPI | Integration tests (API endpoints) | ✅ Memory service accessible |
| **4** | Agent Integration + Profiles | E2E tests (personalization scenario) | ✅ **Phase 1 Complete** |

### Phase 2: Enhancement (Weeks 5-8)

| Week | Deliverable | Tests | Milestone |
|------|-------------|-------|-----------|
| **5-6** | FastMCP Server + MCP Transport | Integration tests (MCP resources/tools) | ✅ Local resource access |
| **7-8** | Redis Cache + Performance Tuning | Performance tests (latency, load) | ✅ **Phase 2 Complete** |

### Phase 3: Enterprise (Weeks 9-12)

| Week | Deliverable | Tests | Milestone |
|------|-------------|-------|-----------|
| **9-10** | gRPC Transport + Proto Definitions | Integration tests (gRPC service) | ✅ Enterprise transport ready |
| **11-12** | Cloud SQL Migration (optional) | Migration tests, performance comparison | ✅ **Phase 3 Complete** |

---

## 12. Success Criteria

### 12.1 Per-Phase Success Metrics

**Phase 1 Success:**
- [ ] All agents can access memory via HTTP
- [ ] Personalized recommendations work for `scholar_001`
- [ ] Anonymous users (`new_user_004`) can use system without memory
- [ ] Test coverage >90% for core interfaces

**Phase 2 Success:**
- [ ] MCP transport provides <50ms latency for local access
- [ ] Redis cache reduces embedding API calls by >60%
- [ ] Load test: 100 concurrent users with <500ms p95 latency

**Phase 3 Success:**
- [ ] gRPC transport handles >1000 QPS
- [ ] A2A memory federation works between two libraries
- [ ] (Optional) Cloud SQL performs equivalent to Firestore

### 12.2 Overall Project Success

**The memory system proves successful when:**
1. ✅ An AI agent uses patron history to make accurate recommendations
2. ✅ The system scales to 100+ concurrent users with <500ms latency
3. ✅ Storage backend can be swapped (Firestore ↔ Cloud SQL) without changing agent code
4. ✅ Transport protocol can be upgraded (HTTP → MCP → gRPC) without breaking existing agents
5. ✅ Evaluation scenarios demonstrate measurable improvement in personalization vs. baseline
6. ✅ Privacy consent is enforced at all tiers (working, episodic, semantic)
7. ✅ TDD approach enables systematic bug identification and resolution

---

## 13. Risk Mitigation

### 13.1 Technical Risks

| Risk | Mitigation | Contingency |
|------|-----------|-------------|
| **Firestore limitations for vector search** | Start small (<10k embeddings), monitor performance | Migrate to Cloud SQL + pgvector if needed |
| **MCP adoption complexity** | Use FastMCP (simplifies server setup) | Fall back to HTTP-only if MCP proves difficult |
| **gRPC learning curve** | Defer to Phase 3, use HTTP/MCP until proven necessary | Skip gRPC if HTTP + MCP meet performance needs |
| **Vertex AI embedding costs** | Cache aggressively, batch requests | Switch to open-source embeddings (e.g., sentence-transformers) |
| **ADK limitations** | Abstract behind IMemoryTransport interface | Switch agent framework if needed (agents don't depend on ADK) |

### 13.2 Scope Risks

| Risk | Mitigation |
|------|-----------|
| **Feature creep** | Stick to phase deliverables, defer "nice-to-haves" to Phase 4 |
| **Over-engineering** | Start with simplest implementation (in-memory, HTTP), iterate based on tests |
| **Test neglect** | Mandate >90% coverage, block PRs that reduce coverage |

---

## 14. Next Steps

### 14.1 Immediate Actions (This Week)

1. **Create Repository Structure:**
   ```bash
   mkdir -p services/memory/{app,tests}
   mkdir -p memory/{interfaces,stores,services,transports,embeddings,profiles}
   mkdir -p tests/{unit,integration,performance,evaluation/scenarios/memory}
   ```

2. **Write First Test:**
   - Create `tests/unit/test_memory_store.py`
   - Write failing test for `InMemoryStore.save_interaction()`
   - Implement `InMemoryStore` to make test pass

3. **Document Interfaces:**
   - Write docstrings for `IMemoryStore`, `IMemoryService`, `IMemoryTransport`
   - Add type hints and examples

4. **Set Up CI/CD:**
   - Configure pytest with coverage reporting
   - Add pre-commit hooks for linting (black, mypy, ruff)

### 14.2 Phase 1 Kickoff Checklist

- [ ] Development environment configured (Python 3.11+, poetry, pytest)
- [ ] Firestore emulator running locally (`gcloud emulators firestore start`)
- [ ] Vertex AI credentials configured (`GOOGLE_APPLICATION_CREDENTIALS`)
- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] First test written and passing (`pytest tests/unit/test_memory_store.py`)

---

## 15. Appendix: Related Documentation

- **[MEMORY_SYSTEM.md](./MEMORY_SYSTEM.md)** - Memory architecture and tiers
- **[MEMORY_SYSTEM_ARCHITECTURE.md](./MEMORY_SYSTEM_ARCHITECTURE.md)** - Architectural pattern exploration
- **[AGENTS.md](./AGENTS.md)** - Agent hierarchy and tool definitions
- **[DATA_MODEL.md](./DATA_MODEL.md)** - Database schemas
- **[A2A_PROTOCOL.md](./A2A_PROTOCOL.md)** - Inter-library communication
- **[EVALUATION.md](./EVALUATION.md)** - Evaluation framework and scenarios

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-02 | System | Initial development roadmap created |

---

**END OF DOCUMENT**
