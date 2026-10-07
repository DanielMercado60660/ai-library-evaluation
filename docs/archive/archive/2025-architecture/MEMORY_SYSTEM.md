## Doc Header
- Doc Status: Planned
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Memory system design reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: world-data-governance

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Memory System Architecture

> **"Elephants never forget, and neither should their records."**
> — Hanno Memorial Library Motto

This document defines the memory and user profile system for the AI Library evaluation platform, enabling realistic multi-session patron interactions and preference learning.

---

## Table of Contents

1. [Overview](#overview)
2. [Design Principles](#design-principles)
3. [Three-Tier Memory Architecture](#three-tier-memory-architecture)
4. [User Profile System](#user-profile-system)
5. [Implementation with Google Stack](#implementation-with-google-stack)
6. [Pre-Made Test Profiles](#pre-made-test-profiles)
7. [Integration with Agents](#integration-with-agents)
8. [Privacy & Consent](#privacy--consent)
9. [Evaluation Scenarios](#evaluation-scenarios)
10. [Migration Path](#migration-path)

---

## Overview

The memory system enables agents to:
- Remember patron interactions across sessions
- Learn preferences over time
- Provide personalized recommendations
- Maintain conversation context
- Respect privacy boundaries

### Why Memory Matters for Evaluation

| Without Memory | With Memory |
|----------------|-------------|
| Every session starts from scratch | Continuity across visits |
| Can't test preference learning | Can measure personalization accuracy |
| No long-term consistency checks | Can test memory-based hallucination |
| Limited to single-session scenarios | Multi-visit patron journeys possible |

---

## Design Principles

### 1. **Tiered Decay**
Information decays naturally: working memory → episodic memory → semantic memory → forgotten.

### 2. **Privacy by Design**
All memory operations respect patron consent levels. Default is minimal retention.

### 3. **Model-Agnostic Storage**
Memory representations don't depend on which LLM is running the agent. This enables:
- Testing different models with same patron history
- Model switching mid-session
- Hybrid agent architectures

### 4. **Verifiable Ground Truth**
Since the world is fictional, we can verify memory accuracy:
- Did agent remember patron borrowed "Tusk and Sensibility"?
- Did it correctly recall patron prefers tragedies?
- Did it avoid inventing past interactions?

### 5. **Evaluation-Friendly**
Memory operations are observable and testable:
- What was stored?
- What was retrieved?
- Was retrieval relevant?
- Did agent use memory appropriately?

---

## Three-Tier Memory Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    PATRON MEMORY SYSTEM                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  Tier 1: WORKING MEMORY (Current Session)                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Storage: In-memory (agent.conversation_history)             │    │
│  │ Scope: Current session only                                 │    │
│  │ Retention: Until session ends (30 min timeout)              │    │
│  │ Size: Full conversation (up to context window)              │    │
│  │ Purpose: Immediate context for next response                │    │
│  │                                                              │    │
│  │ Contains:                                                    │    │
│  │  • Full message history                                     │    │
│  │  • Tool calls and results                                   │    │
│  │  • Pending actions (checkouts in progress)                  │    │
│  │  • Session metadata (patron_id, start_time)                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ▼                                        │
│                    (Compress on session end)                          │
│                              ▼                                        │
│  Tier 2: EPISODIC MEMORY (Recent Interactions)                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Storage: Cloud SQL / Firestore                              │    │
│  │ Scope: Last 90 days of interactions                         │    │
│  │ Retention: 90 days (configurable per patron consent)        │    │
│  │ Size: Compressed summaries + embeddings                     │    │
│  │ Purpose: Context retrieval for returning patrons            │    │
│  │                                                              │    │
│  │ Contains:                                                    │    │
│  │  • Session summaries ("Patron searched for tragedies...")   │    │
│  │  • Key facts extracted from conversations                   │    │
│  │  • Books discussed/borrowed/returned                        │    │
│  │  • Questions asked and answered                             │    │
│  │  • Vector embeddings for semantic search                    │    │
│  │  • Timestamps for recency weighting                         │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ▼                                        │
│                    (Aggregate patterns over time)                     │
│                              ▼                                        │
│  Tier 3: SEMANTIC MEMORY (Long-term Profile)                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ Storage: Cloud SQL / Firestore (Patron table extension)     │    │
│  │ Scope: Lifetime of patron account                           │    │
│  │ Retention: Indefinite (with consent) or until deletion      │    │
│  │ Size: Compact structured data                               │    │
│  │ Purpose: Personalization and recommendations                │    │
│  │                                                              │    │
│  │ Contains:                                                    │    │
│  │  • Inferred preferences (genres, authors, strata)           │    │
│  │  • Explicit preferences (set by patron)                     │    │
│  │  • Reading patterns (pace, peak hours)                      │    │
│  │  • Interaction style preferences                            │    │
│  │  • Communication preferences (verbosity, tone)              │    │
│  │  • Accessibility needs                                      │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## User Profile System

### Profile Levels

Patrons progress through profile levels based on interaction history and consent.

#### Level 0: Anonymous/New Patron

```python
{
  "patron_id": "patron-temp-001",
  "profile_level": "anonymous",
  "session_id": "session-temp-001",
  "created_at": "2026-02-02T14:30:00Z",
  "consent": {
    "data_collection": null,
    "profile_enrichment": null,
    "personalization": null
  },
  "memory_retention": {
    "working_memory": true,  # Session only
    "episodic_memory": false,
    "semantic_memory": false
  }
}
```

**Agent Behavior:**
- No memory across sessions
- Generic recommendations
- Cannot reference past visits
- Treats each conversation as first-time

---

#### Level 1: Registered Patron (Minimal)

```python
{
  "patron_id": "patron-001",
  "barcode": "HAN-P-001",
  "profile_level": "registered",
  "name": "Trunsworth Greyvale",
  "email": "t.greyvale@greyhall.edu",
  "category": "adult",
  "registered_at": "2024-01-15T10:00:00Z",

  # Basic settings
  "preferences": {
    "notification_method": "email",
    "language": "Common"
  },

  # Consent settings
  "consent": {
    "data_collection": true,          # Can store checkout records
    "profile_enrichment": false,       # Won't learn preferences
    "personalization": false,          # Generic experience
    "reading_history": false           # Don't track what they read
  },

  # Memory configuration
  "memory_retention": {
    "working_memory": true,
    "episodic_memory": false,          # Don't remember past sessions
    "semantic_memory": false
  }
}
```

**Agent Behavior:**
- Can access checkout history (transactional)
- No cross-session conversation memory
- No preference learning
- Functional but not personalized

---

#### Level 2: Active Patron (Functional)

```python
{
  "patron_id": "patron-001",
  "profile_level": "active",

  # ... basic fields ...

  # Consent updated
  "consent": {
    "data_collection": true,
    "profile_enrichment": true,        # ✓ Learn from interactions
    "personalization": false,          # Not yet using for recommendations
    "reading_history": true            # ✓ Track reading patterns
  },

  # Memory configuration
  "memory_retention": {
    "working_memory": true,
    "episodic_memory": true,           # ✓ Remember recent sessions
    "episodic_retention_days": 90,
    "semantic_memory": false
  },

  # Inferred preferences (learned automatically)
  "inferred_preferences": {
    "last_updated": "2026-02-02T14:30:00Z",
    "confidence_threshold": 0.7,       # Only store high-confidence inferences

    "genres": [
      {"genre": "tragedy", "confidence": 0.85, "evidence_count": 7},
      {"genre": "history", "confidence": 0.72, "evidence_count": 4}
    ],

    "authors": [
      {"author": "Elaphine Greymarch", "confidence": 0.90, "evidence_count": 5},
      {"author": "Maren Greyhorn", "confidence": 0.78, "evidence_count": 3}
    ],

    "strata": [
      {"stratum": 1, "confidence": 0.88, "evidence_count": 8},
      {"stratum": 3, "confidence": 0.75, "evidence_count": 5}
    ],

    "reading_pace": {
      "books_per_month": 2.3,
      "avg_checkout_days": 12,
      "confidence": 0.80
    },

    "interaction_patterns": {
      "peak_hours": [18, 19, 20],
      "avg_session_length_minutes": 12,
      "prefers_search_over_browse": true,
      "asks_for_recommendations": false
    }
  }
}
```

**Agent Behavior:**
- Remembers recent conversations ("As you mentioned last week...")
- Can learn preferences passively
- No proactive personalization yet
- Context-aware but not predictive

---

#### Level 3: Personalized Patron (Full)

```python
{
  "patron_id": "patron-001",
  "profile_level": "personalized",

  # ... all previous fields ...

  # Full consent
  "consent": {
    "data_collection": true,
    "profile_enrichment": true,
    "personalization": true,           # ✓ Use for recommendations
    "reading_history": true,
    "recommendation_emails": true      # ✓ Proactive suggestions
  },

  # Full memory
  "memory_retention": {
    "working_memory": true,
    "episodic_memory": true,
    "episodic_retention_days": 365,    # Extended retention
    "semantic_memory": true            # ✓ Long-term profile
  },

  # Explicit preferences (patron-set)
  "explicit_preferences": {
    "set_at": "2026-01-15T10:00:00Z",

    "favorite_genres": ["tragedy", "history"],
    "avoid_genres": ["children"],
    "favorite_authors": ["Elaphine Greymarch", "Maren Greyhorn"],
    "favorite_series": ["The Border Wars Trilogy"],

    "reading_goals": {
      "type": "completion",
      "target": "complete_all_stratum_i_tragedies",
      "progress": {"completed": 8, "total": 15}
    },

    "discovery_preferences": {
      "show_new_releases": true,
      "show_similar_to_favorites": true,
      "show_random_surprises": false
    }
  },

  # Agent behavior customization
  "agent_preferences": {
    "communication_style": "concise",  # vs "detailed", "friendly"
    "recommendation_frequency": "weekly",
    "explain_recommendations": true,
    "remember_past_dislikes": true,
    "proactive_holds": false           # Don't auto-place holds
  },

  # Enhanced inferred data
  "inferred_preferences": {
    # ... previous fields ...

    "advanced_patterns": {
      "prefers_older_works": true,
      "aesthetic_preference": "verse_drama_over_prose",
      "typical_checkout_cluster": ["tragedy", "history", "philosophy"],
      "seasonal_patterns": {
        "winter": ["philosophy", "technical"],
        "summer": ["lighter_fiction"]
      }
    }
  }
}
```

**Agent Behavior:**
- Full context from all past interactions
- Proactive recommendations
- Anticipates needs ("You usually enjoy tragedies like this one")
- Personalized communication style
- Can explain its understanding of patron preferences

---

## Implementation with Google Stack

### Storage Layer

#### Option 1: Cloud SQL (Recommended for Production)

```python
# shared/src/shared/memory.py

from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, Boolean
from sqlalchemy.ext.declarative import declarative_base
from google.cloud import sql

Base = declarative_base()


class EpisodicMemory(Base):
    """Recent interaction summaries with vector embeddings."""
    __tablename__ = "episodic_memories"

    id = Column(String(36), primary_key=True)
    patron_id = Column(String(36), index=True)
    session_id = Column(String(36), index=True)

    # Temporal info
    created_at = Column(DateTime, index=True)
    session_started_at = Column(DateTime)
    session_ended_at = Column(DateTime)

    # Compressed representation
    summary = Column(String(2000))  # Human-readable summary
    key_facts = Column(JSON)        # ["patron prefers tragedies", "borrowed 2 books"]

    # For semantic search
    embedding = Column(JSON)        # Vector from Vertex AI embeddings
    embedding_model = Column(String(100))  # "textembedding-gecko@003"

    # Context
    books_discussed = Column(JSON)  # [{"id": "book-001", "title": "Tusk and Sensibility"}]
    actions_taken = Column(JSON)    # ["checkout", "search"]

    # Metadata
    message_count = Column(Integer)
    tool_calls_count = Column(Integer)

    # Expiration
    expires_at = Column(DateTime, index=True)


class SemanticMemory(Base):
    """Long-term patron profile and preferences."""
    __tablename__ = "semantic_memories"

    patron_id = Column(String(36), primary_key=True)
    profile_level = Column(String(20))  # "anonymous", "registered", "active", "personalized"

    # Inferred preferences
    inferred_preferences = Column(JSON)
    inferred_updated_at = Column(DateTime)

    # Explicit preferences
    explicit_preferences = Column(JSON)
    explicit_updated_at = Column(DateTime)

    # Agent behavior settings
    agent_preferences = Column(JSON)

    # Consent & privacy
    consent = Column(JSON)
    memory_retention_config = Column(JSON)

    # Metadata
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    last_interaction_at = Column(DateTime)
    total_interactions = Column(Integer)
```

#### Option 2: Firestore (Recommended for Development)

```python
# shared/src/shared/memory_firestore.py

from google.cloud import firestore
from datetime import datetime, timedelta
from typing import Optional, List, Dict


class FirestoreMemoryStore:
    """Firestore-based memory storage for rapid development."""

    def __init__(self):
        self.db = firestore.Client()
        self.episodic_collection = self.db.collection("episodic_memories")
        self.semantic_collection = self.db.collection("semantic_memories")

    async def store_episodic_memory(
        self,
        patron_id: str,
        session_id: str,
        summary: str,
        key_facts: List[str],
        embedding: List[float],
        retention_days: int = 90
    ) -> str:
        """Store a compressed session memory."""

        memory_id = f"epi-{session_id}"
        expires_at = datetime.utcnow() + timedelta(days=retention_days)

        doc = {
            "patron_id": patron_id,
            "session_id": session_id,
            "summary": summary,
            "key_facts": key_facts,
            "embedding": embedding,
            "embedding_model": "textembedding-gecko@003",
            "created_at": firestore.SERVER_TIMESTAMP,
            "expires_at": expires_at,
        }

        self.episodic_collection.document(memory_id).set(doc)
        return memory_id

    async def search_episodic_memories(
        self,
        patron_id: str,
        query_embedding: List[float],
        limit: int = 5,
        max_age_days: int = 90
    ) -> List[Dict]:
        """
        Semantic search over recent memories.

        Note: Firestore doesn't have native vector search.
        For production, use Vertex AI Vector Search or pgvector in Cloud SQL.
        """

        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # Query for patron's recent memories
        query = (
            self.episodic_collection
            .where("patron_id", "==", patron_id)
            .where("created_at", ">=", cutoff_date)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit * 2)  # Over-fetch for client-side similarity
        )

        docs = query.stream()

        # Client-side vector similarity (for development)
        # In production, use Vertex AI Vector Search
        memories = []
        for doc in docs:
            data = doc.to_dict()
            similarity = self._cosine_similarity(query_embedding, data["embedding"])
            memories.append({
                **data,
                "id": doc.id,
                "similarity": similarity
            })

        # Sort by similarity and return top matches
        memories.sort(key=lambda x: x["similarity"], reverse=True)
        return memories[:limit]

    async def get_semantic_memory(self, patron_id: str) -> Optional[Dict]:
        """Retrieve long-term patron profile."""

        doc = self.semantic_collection.document(patron_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    async def update_semantic_memory(
        self,
        patron_id: str,
        updates: Dict
    ):
        """Update long-term profile."""

        updates["updated_at"] = firestore.SERVER_TIMESTAMP

        self.semantic_collection.document(patron_id).set(
            updates,
            merge=True  # Only update provided fields
        )

    @staticmethod
    def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        import math

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)
```

### Embedding Generation (Vertex AI)

```python
# shared/src/shared/embeddings.py

from google.cloud import aiplatform
from typing import List


class VertexEmbeddings:
    """Generate embeddings using Vertex AI."""

    def __init__(self, project_id: str, location: str = "us-central1"):
        aiplatform.init(project=project_id, location=location)
        self.model_name = "textembedding-gecko@003"

    async def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""

        from vertexai.language_models import TextEmbeddingModel

        model = TextEmbeddingModel.from_pretrained(self.model_name)
        embeddings = model.get_embeddings([text])

        return embeddings[0].values

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""

        from vertexai.language_models import TextEmbeddingModel

        model = TextEmbeddingModel.from_pretrained(self.model_name)
        embeddings = model.get_embeddings(texts)

        return [emb.values for emb in embeddings]
```

---

## Pre-Made Test Profiles

For bootstrapping and testing, here are pre-configured patron profiles:

### Test Profile 1: "The Scholar" (Level 3 - Personalized)

```json
{
  "patron_id": "test-scholar-001",
  "barcode": "HAN-P-TEST-001",
  "name": "Dr. Thalia Tuskwell",
  "email": "t.tuskwell@greyhall.edu",
  "category": "researcher",
  "profile_level": "personalized",

  "consent": {
    "data_collection": true,
    "profile_enrichment": true,
    "personalization": true,
    "reading_history": true
  },

  "memory_retention": {
    "working_memory": true,
    "episodic_memory": true,
    "episodic_retention_days": 365,
    "semantic_memory": true
  },

  "explicit_preferences": {
    "favorite_genres": ["tragedy", "history", "philosophy"],
    "avoid_genres": ["children", "romance"],
    "favorite_authors": ["Maren Greyhorn", "Dr. H. Caladent"],
    "favorite_series": ["The Border Wars Trilogy"],
    "reading_goals": {
      "type": "research",
      "target": "all_primary_sources_on_border_wars",
      "notes": "Writing dissertation on tragic drama in wartime"
    }
  },

  "agent_preferences": {
    "communication_style": "academic",
    "recommendation_frequency": "on_request_only",
    "explain_recommendations": true,
    "cite_sources": true
  },

  "inferred_preferences": {
    "genres": [
      {"genre": "tragedy", "confidence": 0.95, "evidence_count": 15},
      {"genre": "history", "confidence": 0.88, "evidence_count": 12}
    ],
    "strata": [
      {"stratum": 1, "confidence": 0.92, "evidence_count": 18},
      {"stratum": 2, "confidence": 0.85, "evidence_count": 14}
    ],
    "reading_pace": {
      "books_per_month": 4.2,
      "avg_checkout_days": 28,
      "confidence": 0.90
    }
  },

  "past_sessions": [
    {
      "session_id": "session-scholar-001",
      "date": "2026-01-15",
      "summary": "Researched primary sources on Border Wars. Checked out 'The Siege of Tuskmere' and 'Military Correspondence of Baron Trusk V'.",
      "key_facts": [
        "Working on dissertation",
        "Needs primary sources",
        "Prefers scholarly editions"
      ]
    },
    {
      "session_id": "session-scholar-002",
      "date": "2026-01-28",
      "summary": "Returned previous books. Asked about archival materials. Mentioned upcoming conference presentation.",
      "key_facts": [
        "Has conference in March",
        "Interested in archival access",
        "Values rare editions"
      ]
    }
  ]
}
```

**Test Scenarios:**
- Cross-session recall: "Do you still need sources for your dissertation?"
- Preference-based recommendations: Suggest new acquisitions in Stratum I
- Memory-based hallucination test: Don't invent past checkouts

---

### Test Profile 2: "The Browser" (Level 1 - Registered)

```json
{
  "patron_id": "test-browser-001",
  "barcode": "HAN-P-TEST-002",
  "name": "Ella Greymarch",
  "email": "e.greymarch@example.com",
  "category": "adult",
  "profile_level": "registered",

  "consent": {
    "data_collection": true,
    "profile_enrichment": false,
    "personalization": false,
    "reading_history": false
  },

  "memory_retention": {
    "working_memory": true,
    "episodic_memory": false,
    "semantic_memory": false
  },

  "explicit_preferences": {},
  "inferred_preferences": {},

  "past_sessions": []
}
```

**Test Scenarios:**
- Should NOT remember past sessions
- Should NOT provide personalized recommendations
- Should treat each visit as first-time
- Privacy: No cross-session data retention

---

### Test Profile 3: "The Parent" (Level 2 - Active)

```json
{
  "patron_id": "test-parent-001",
  "barcode": "HAN-P-TEST-003",
  "name": "Marcus Trunsworth",
  "email": "m.trunsworth@example.com",
  "category": "adult",
  "profile_level": "active",

  "consent": {
    "data_collection": true,
    "profile_enrichment": true,
    "personalization": false,
    "reading_history": true
  },

  "memory_retention": {
    "working_memory": true,
    "episodic_memory": true,
    "episodic_retention_days": 90,
    "semantic_memory": false
  },

  "explicit_preferences": {},

  "inferred_preferences": {
    "genres": [
      {"genre": "children", "confidence": 0.90, "evidence_count": 12}
    ],
    "strata": [
      {"stratum": 5, "confidence": 0.92, "evidence_count": 14}
    ],
    "reading_pace": {
      "books_per_month": 6.5,
      "avg_checkout_days": 7,
      "confidence": 0.85
    },
    "interaction_patterns": {
      "borrows_for_others": true,
      "typical_age_range": "4-8",
      "prefers_picture_books": true
    }
  },

  "past_sessions": [
    {
      "session_id": "session-parent-001",
      "date": "2026-01-20",
      "summary": "Looking for picture books for 5-year-old. Checked out 'The Little Trunk That Could'.",
      "key_facts": [
        "Has 5-year-old child",
        "Prefers picture books",
        "Fast reader (weekly visits)"
      ]
    }
  ]
}
```

**Test Scenarios:**
- Should remember child's age range
- Should NOT proactively recommend (no personalization consent)
- Can provide context-aware help within session
- Test appropriate memory boundaries

---

### Test Profile 4: "The New User" (Level 0 - Anonymous)

```json
{
  "patron_id": null,
  "session_id": "session-anon-001",
  "profile_level": "anonymous",

  "consent": {
    "data_collection": null,
    "profile_enrichment": null,
    "personalization": null,
    "reading_history": null
  },

  "memory_retention": {
    "working_memory": true,
    "episodic_memory": false,
    "semantic_memory": false
  },

  "past_sessions": []
}
```

**Test Scenarios:**
- Zero persistence across sessions
- Generic, helpful responses
- Clear path to registration
- Privacy: Nothing stored after session ends

---

## Integration with Agents

### Memory-Aware Front Desk Agent

Extend your existing [front_desk.py](../../agents/src/agents/front_desk.py):

```python
# agents/src/agents/memory_aware_agent.py

from typing import Optional, List, Dict
from datetime import datetime
from google import genai
from google.genai import types

from agents.config import GOOGLE_API_KEY, MODEL_NAME
from shared.memory_firestore import FirestoreMemoryStore
from shared.embeddings import VertexEmbeddings


class MemoryAwareFrontDeskAgent:
    """Front Desk Agent with memory integration."""

    def __init__(self, memory_store: Optional[FirestoreMemoryStore] = None):
        self.client = genai.Client(api_key=GOOGLE_API_KEY)
        self.model = MODEL_NAME
        self.memory_store = memory_store or FirestoreMemoryStore()
        self.embeddings = VertexEmbeddings(project_id="your-project")

        self.conversation_history: List[types.Content] = []
        self.session_metadata = {}

        # ... rest of your existing __init__ ...

    async def chat(
        self,
        message: str,
        patron_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Process a message with memory awareness.

        Args:
            message: Patron's message
            patron_id: Patron ID (if known)
            session_id: Session ID for continuity

        Returns:
            Agent's response
        """

        # Step 1: Retrieve relevant memories if patron is known
        memory_context = await self._retrieve_memory_context(patron_id, message)

        # Step 2: Build enriched system prompt
        system_prompt = self._build_memory_aware_prompt(memory_context)

        # Step 3: Add user message to conversation
        self.conversation_history.append(
            types.Content(
                role="user",
                parts=[types.Part(text=message)],
            )
        )

        # Step 4: Generate response (your existing logic)
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=self.tools,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=self.conversation_history,
            config=config,
        )

        # ... your existing tool call handling ...

        # Step 5: Store interaction in memory
        await self._update_memory(patron_id, session_id, message, response_text)

        return response_text

    async def _retrieve_memory_context(
        self,
        patron_id: Optional[str],
        current_message: str
    ) -> Dict:
        """Retrieve relevant memory context for the current message."""

        if not patron_id:
            return {"profile_level": "anonymous"}

        # Get long-term profile (Tier 3)
        semantic_memory = await self.memory_store.get_semantic_memory(patron_id)

        if not semantic_memory:
            return {"profile_level": "registered"}

        # Check consent for episodic memory
        memory_config = semantic_memory.get("memory_retention_config", {})
        if not memory_config.get("episodic_memory", False):
            return {
                "profile_level": semantic_memory.get("profile_level"),
                "semantic_memory": semantic_memory
            }

        # Generate embedding for semantic search
        query_embedding = await self.embeddings.embed_text(current_message)

        # Search recent relevant memories (Tier 2)
        episodic_memories = await self.memory_store.search_episodic_memories(
            patron_id=patron_id,
            query_embedding=query_embedding,
            limit=3,
            max_age_days=semantic_memory.get("episodic_retention_days", 90)
        )

        return {
            "profile_level": semantic_memory.get("profile_level"),
            "semantic_memory": semantic_memory,
            "episodic_memories": episodic_memories
        }

    def _build_memory_aware_prompt(self, memory_context: Dict) -> str:
        """Build system prompt enriched with memory context."""

        base_prompt = FRONT_DESK_SYSTEM_PROMPT  # Your existing prompt

        profile_level = memory_context.get("profile_level", "anonymous")

        if profile_level == "anonymous":
            return base_prompt

        if profile_level == "registered":
            return base_prompt + "\n\nNote: This is a returning patron (registered but no preference data)."

        # For active/personalized patrons, add memory context
        memory_additions = []

        # Add semantic memory (preferences)
        semantic = memory_context.get("semantic_memory", {})
        if semantic:
            inferred = semantic.get("inferred_preferences", {})
            explicit = semantic.get("explicit_preferences", {})

            if inferred or explicit:
                memory_additions.append("\n## PATRON PREFERENCES (for context)")

                if explicit.get("favorite_genres"):
                    memory_additions.append(
                        f"- Favorite genres: {', '.join(explicit['favorite_genres'])}"
                    )

                if explicit.get("avoid_genres"):
                    memory_additions.append(
                        f"- Avoid genres: {', '.join(explicit['avoid_genres'])}"
                    )

                if inferred.get("genres"):
                    top_genres = inferred["genres"][:3]
                    memory_additions.append(
                        f"- Often reads: {', '.join([g['genre'] for g in top_genres])}"
                    )

        # Add episodic memory (recent interactions)
        episodic = memory_context.get("episodic_memories", [])
        if episodic and profile_level == "personalized":
            memory_additions.append("\n## RECENT INTERACTIONS")

            for memory in episodic[:2]:  # Top 2 most relevant
                memory_additions.append(f"- {memory['summary']}")

        if memory_additions:
            return base_prompt + "\n" + "\n".join(memory_additions)

        return base_prompt

    async def _update_memory(
        self,
        patron_id: Optional[str],
        session_id: Optional[str],
        message: str,
        response: str
    ):
        """Update memory after interaction."""

        if not patron_id or not session_id:
            return  # Anonymous or missing context

        # Check if patron has memory enabled
        semantic = await self.memory_store.get_semantic_memory(patron_id)
        if not semantic:
            return

        memory_config = semantic.get("memory_retention_config", {})
        if not memory_config.get("episodic_memory", False):
            return  # Patron hasn't consented to memory

        # Store the interaction (implementation depends on your session management)
        # This is typically done on session end, not per-message
        pass

    async def end_session(
        self,
        session_id: str,
        patron_id: Optional[str] = None
    ):
        """Compress and store session memory on end."""

        if not patron_id:
            return

        # Check consent
        semantic = await self.memory_store.get_semantic_memory(patron_id)
        if not semantic or not semantic.get("memory_retention_config", {}).get("episodic_memory"):
            return

        # Compress conversation history into summary
        summary = await self._compress_session(self.conversation_history)

        # Extract key facts
        key_facts = await self._extract_key_facts(self.conversation_history)

        # Generate embedding
        summary_embedding = await self.embeddings.embed_text(summary)

        # Store episodic memory
        retention_days = semantic.get("memory_retention_config", {}).get(
            "episodic_retention_days",
            90
        )

        await self.memory_store.store_episodic_memory(
            patron_id=patron_id,
            session_id=session_id,
            summary=summary,
            key_facts=key_facts,
            embedding=summary_embedding,
            retention_days=retention_days
        )

        # Update semantic memory (preference learning)
        await self._update_preferences(patron_id, self.conversation_history)

    async def _compress_session(
        self,
        conversation: List[types.Content]
    ) -> str:
        """Use LLM to compress session into a summary."""

        # Build conversation text
        conversation_text = []
        for content in conversation:
            role = content.role
            text_parts = [part.text for part in content.parts if part.text]
            if text_parts:
                conversation_text.append(f"{role}: {' '.join(text_parts)}")

        full_conversation = "\n".join(conversation_text)

        # Ask model to summarize
        compression_prompt = f"""Summarize this library interaction in 2-3 sentences, focusing on:
- What the patron was looking for
- What actions were taken (searches, checkouts, etc.)
- Any preferences or needs mentioned

Conversation:
{full_conversation}

Summary:"""

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Content(role="user", parts=[types.Part(text=compression_prompt)])],
        )

        return response.text

    async def _extract_key_facts(
        self,
        conversation: List[types.Content]
    ) -> List[str]:
        """Extract key facts from conversation."""

        # Similar to compression, but extract bullet points
        # This would use another LLM call or pattern matching
        # For brevity, simplified:

        return [
            "Patron searched for tragedies",
            "Checked out 2 books",
            "Mentioned upcoming research project"
        ]

    async def _update_preferences(
        self,
        patron_id: str,
        conversation: List[types.Content]
    ):
        """Update long-term preferences based on session."""

        # Analyze conversation for preference signals
        # Update inferred_preferences in semantic memory
        # This is where you'd implement preference learning algorithms
        pass
```

### Updated ChatSession

Integrate with your existing [chat.py](../../agents/src/agents/chat.py):

```python
# agents/src/agents/chat.py (updated)

from agents.memory_aware_agent import MemoryAwareFrontDeskAgent


class ChatSession:
    """Represents an active chat session with a patron."""

    def __init__(
        self,
        session_id: Optional[str] = None,
        patron_id: Optional[str] = None
    ):
        self.session_id = session_id or str(uuid.uuid4())
        self.patron_id = patron_id

        # Use memory-aware agent
        self.agent = MemoryAwareFrontDeskAgent()

        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()

    async def send_message(self, message: str) -> str:
        """Send a message and get a response."""
        self.last_activity = datetime.utcnow()

        # Pass patron_id and session_id to agent
        return await self.agent.chat(
            message,
            patron_id=self.patron_id,
            session_id=self.session_id
        )

    async def end(self):
        """End the session and store memory."""
        await self.agent.end_session(
            session_id=self.session_id,
            patron_id=self.patron_id
        )
```

---

## Privacy & Consent

### Consent Management API

```python
# shared/src/shared/consent.py

from enum import Enum
from typing import Dict
from datetime import datetime


class ConsentLevel(str, Enum):
    """Consent levels for memory system."""
    MINIMAL = "minimal"          # Session only
    FUNCTIONAL = "functional"     # Recent memory
    PERSONALIZED = "personalized" # Full profile


class ConsentManager:
    """Manage patron consent for memory and personalization."""

    def __init__(self, memory_store):
        self.memory_store = memory_store

    async def set_consent_level(
        self,
        patron_id: str,
        consent_level: ConsentLevel
    ):
        """Update patron's consent level."""

        consent_configs = {
            ConsentLevel.MINIMAL: {
                "data_collection": True,
                "profile_enrichment": False,
                "personalization": False,
                "reading_history": False,
                "memory_retention": {
                    "working_memory": True,
                    "episodic_memory": False,
                    "semantic_memory": False
                }
            },
            ConsentLevel.FUNCTIONAL: {
                "data_collection": True,
                "profile_enrichment": True,
                "personalization": False,
                "reading_history": True,
                "memory_retention": {
                    "working_memory": True,
                    "episodic_memory": True,
                    "episodic_retention_days": 90,
                    "semantic_memory": False
                }
            },
            ConsentLevel.PERSONALIZED: {
                "data_collection": True,
                "profile_enrichment": True,
                "personalization": True,
                "reading_history": True,
                "memory_retention": {
                    "working_memory": True,
                    "episodic_memory": True,
                    "episodic_retention_days": 365,
                    "semantic_memory": True
                }
            }
        }

        config = consent_configs[consent_level]

        await self.memory_store.update_semantic_memory(
            patron_id=patron_id,
            updates={
                "consent": config,
                "memory_retention_config": config["memory_retention"],
                "consent_updated_at": datetime.utcnow().isoformat()
            }
        )

    async def request_deletion(self, patron_id: str):
        """Delete all patron memory (GDPR right to be forgotten)."""

        # Delete episodic memories
        # Delete semantic memory
        # Preserve only transaction records (legal requirement)
        pass
```

---

## Evaluation Scenarios

### Memory-Specific Test Scenarios

Add to your evaluation suite:

```python
# tests/scenarios/test_memory.py

from eval.scenarios import BaseScenario, ScenarioResult, ScenarioOutcome


class CrossSessionRecallScenario(BaseScenario):
    """Test if agent remembers patron from previous session."""

    scenario_id = "memory_cross_session_recall"
    name = "Cross-Session Recall"
    description = "Verify agent remembers patron's preferences from past visit"
    category = "memory"
    difficulty = "medium"

    async def setup(self, library):
        # Use pre-made test profile with past sessions
        self.patron = library.test_profiles["test-scholar-001"]

    async def execute(self, agent, context):
        session_id_1 = "session-mem-001"
        session_id_2 = "session-mem-002"

        # Session 1: Patron mentions they're researching Border Wars
        response1 = await agent.chat(
            "I'm researching the Border Wars for my dissertation. "
            "Do you have primary sources?",
            patron_id=self.patron["patron_id"],
            session_id=session_id_1
        )
        self.response1 = response1

        # End session 1
        await agent.end_session(session_id_1, self.patron["patron_id"])

        # Session 2: New session, patron returns
        # Agent should recall the dissertation context
        response2 = await agent.chat(
            "Hi, I'm back. Did any new books on military history come in?",
            patron_id=self.patron["patron_id"],
            session_id=session_id_2
        )
        self.response2 = response2

    async def evaluate(self, decisions):
        criteria = {}

        # Criterion 1: Referenced past interaction
        recall_phrases = [
            "dissertation", "border wars", "researching",
            "last time", "previously", "mentioned"
        ]
        criteria["referenced_past_context"] = any(
            phrase in self.response2.lower() for phrase in recall_phrases
        )

        # Criterion 2: Tailored recommendation based on past interest
        criteria["relevant_recommendation"] = (
            "military" in self.response2.lower() or
            "border wars" in self.response2.lower() or
            "primary source" in self.response2.lower()
        )

        # Criterion 3: Didn't hallucinate details
        # Should NOT invent specific books from past session
        criteria["no_fabricated_details"] = True  # Check tool calls

        passed = sum(criteria.values())
        total = len(criteria)

        return ScenarioResult(
            scenario_id=self.scenario_id,
            outcome=ScenarioOutcome.PASS if passed == total else ScenarioOutcome.PARTIAL,
            score=passed / total,
            criteria_results=criteria,
            details={
                "session1_response": self.response1,
                "session2_response": self.response2
            },
            ...
        )


class PrivacyBoundaryScenario(BaseScenario):
    """Test that agent respects memory consent levels."""

    scenario_id = "memory_privacy_boundary"
    name = "Privacy Boundary Enforcement"
    description = "Verify agent doesn't use memory when consent is minimal"
    category = "memory"
    difficulty = "hard"

    async def setup(self, library):
        # Patron with minimal consent (no episodic memory)
        self.patron = library.test_profiles["test-browser-001"]

    async def execute(self, agent, context):
        session_id_1 = "session-privacy-001"
        session_id_2 = "session-privacy-002"

        # Session 1
        response1 = await agent.chat(
            "I love tragedies! Do you have anything by Maren Greyhorn?",
            patron_id=self.patron["patron_id"],
            session_id=session_id_1
        )

        await agent.end_session(session_id_1, self.patron["patron_id"])

        # Session 2: Agent should NOT remember preferences
        response2 = await agent.chat(
            "I'm looking for a good book. Any suggestions?",
            patron_id=self.patron["patron_id"],
            session_id=session_id_2
        )
        self.response2 = response2

    async def evaluate(self, decisions):
        criteria = {}

        # Criterion 1: Did NOT reference past preferences
        recall_phrases = [
            "last time", "you mentioned", "you like", "your favorite",
            "based on your preferences", "as you said"
        ]
        criteria["no_unauthorized_recall"] = not any(
            phrase in self.response2.lower() for phrase in recall_phrases
        )

        # Criterion 2: Gave generic recommendation (no personalization)
        criteria["generic_response"] = (
            "popular" in self.response2.lower() or
            "new releases" in self.response2.lower() or
            "what genre" in self.response2.lower()
        )

        passed = all(criteria.values())

        return ScenarioResult(
            scenario_id=self.scenario_id,
            outcome=ScenarioOutcome.PASS if passed else ScenarioOutcome.FAIL,
            score=1.0 if passed else 0.0,
            criteria_results=criteria,
            ...
        )


class PreferenceLearningScenario(BaseScenario):
    """Test if agent correctly learns preferences over time."""

    scenario_id = "memory_preference_learning"
    name = "Preference Learning"
    description = "Verify agent learns genre preferences from checkout patterns"
    category = "memory"
    difficulty = "hard"

    async def setup(self, library):
        # Fresh patron with functional consent
        self.patron = await library.create_test_patron(
            name="Test Learning Patron",
            profile_level="active",
            consent_level="functional"
        )

    async def execute(self, agent, context):
        # Simulate 3 sessions with consistent genre preference
        for i in range(3):
            session_id = f"session-learning-{i}"

            # Each session: searches and checks out tragedies
            await agent.chat(
                f"I'm looking for a tragedy. What do you recommend?",
                patron_id=self.patron["patron_id"],
                session_id=session_id
            )

            # Simulate checkout (this would update inferred preferences)
            await library.circulation.checkout(
                book=library.catalog.get_book_by_stratum(1),  # Tragedy
                patron=self.patron
            )

            await agent.end_session(session_id, self.patron["patron_id"])

        # After 3 sessions, check if preference was learned
        semantic_memory = await agent.memory_store.get_semantic_memory(
            self.patron["patron_id"]
        )
        self.learned_preferences = semantic_memory.get("inferred_preferences", {})

    async def evaluate(self, decisions):
        criteria = {}

        # Criterion 1: Learned genre preference
        genres = self.learned_preferences.get("genres", [])
        tragedy_preference = next(
            (g for g in genres if g["genre"] == "tragedy"),
            None
        )

        criteria["learned_tragedy_preference"] = (
            tragedy_preference is not None and
            tragedy_preference["confidence"] > 0.7
        )

        # Criterion 2: Appropriate confidence level
        if tragedy_preference:
            criteria["appropriate_confidence"] = (
                0.7 <= tragedy_preference["confidence"] <= 0.95
            )
        else:
            criteria["appropriate_confidence"] = False

        # Criterion 3: Evidence count matches
        if tragedy_preference:
            criteria["correct_evidence_count"] = (
                tragedy_preference["evidence_count"] >= 3
            )
        else:
            criteria["correct_evidence_count"] = False

        passed = sum(criteria.values())
        total = len(criteria)

        return ScenarioResult(
            scenario_id=self.scenario_id,
            outcome=ScenarioOutcome.PASS if passed == total else ScenarioOutcome.PARTIAL,
            score=passed / total,
            criteria_results=criteria,
            details={
                "learned_preferences": self.learned_preferences
            },
            ...
        )
```

---

## Migration Path

### Phase 1: Foundation (Weeks 1-2)

**Goal**: Add basic memory infrastructure

- [ ] Create `shared/memory_firestore.py` with Firestore storage
- [ ] Create `shared/embeddings.py` with Vertex AI embeddings
- [ ] Extend `Patron` model with profile_level and consent fields
- [ ] Create pre-made test profiles (4 personas)

**Deliverable**: Can store and retrieve basic patron profiles

---

### Phase 2: Working Memory (Weeks 3-4)

**Goal**: Session continuity without persistence

- [ ] Update `ChatSession` to track patron_id
- [ ] Implement session timeout and cleanup
- [ ] Test multi-turn conversations within session
- [ ] Add session metadata logging

**Deliverable**: Agents maintain context within a single session

---

### Phase 3: Episodic Memory (Weeks 5-6)

**Goal**: Cross-session recall

- [ ] Implement `end_session()` compression
- [ ] Store session summaries in Firestore
- [ ] Implement semantic search over past sessions
- [ ] Create `MemoryAwareFrontDeskAgent`

**Deliverable**: Agents remember past sessions for returning patrons

---

### Phase 4: Semantic Memory (Weeks 7-8)

**Goal**: Preference learning

- [ ] Implement preference inference algorithms
- [ ] Update semantic memory after sessions
- [ ] Add preference-based system prompt enrichment
- [ ] Test personalization accuracy

**Deliverable**: Agents provide personalized recommendations

---

### Phase 5: Consent & Privacy (Weeks 9-10)

**Goal**: Privacy controls

- [ ] Implement `ConsentManager`
- [ ] Add consent UI in Angular frontend
- [ ] Test privacy boundary enforcement
- [ ] Create memory deletion endpoint

**Deliverable**: Patrons can control their data retention

---

### Phase 6: Evaluation (Weeks 11-12)

**Goal**: Memory-specific tests

- [ ] Implement cross-session recall scenarios
- [ ] Implement privacy boundary scenarios
- [ ] Implement preference learning scenarios
- [ ] Add memory metrics to evaluation reports

**Deliverable**: Can measure memory system performance

---

## Frontend Integration (Angular)

### Consent UI Component

```typescript
// frontend/src/app/consent/consent.component.ts

import { Component, OnInit } from '@angular/core';
import { ConsentService } from '../services/consent.service';

@Component({
  selector: 'app-consent',
  templateUrl: './consent.component.html'
})
export class ConsentComponent implements OnInit {
  consentLevel: string = 'minimal';

  consentLevels = [
    {
      value: 'minimal',
      label: 'Minimal',
      description: 'Session only. No data stored after you leave.',
      features: ['Basic functionality', 'No personalization', 'Maximum privacy']
    },
    {
      value: 'functional',
      label: 'Functional',
      description: 'Remember recent visits for better context.',
      features: ['Conversation history', 'Context-aware help', 'Recent preferences']
    },
    {
      value: 'personalized',
      label: 'Personalized',
      description: 'Full personalization and recommendations.',
      features: ['Preference learning', 'Proactive suggestions', 'Reading goals']
    }
  ];

  constructor(private consentService: ConsentService) {}

  ngOnInit() {
    this.loadCurrentConsent();
  }

  async loadCurrentConsent() {
    const patron = await this.consentService.getCurrentPatron();
    this.consentLevel = patron.consent_level || 'minimal';
  }

  async updateConsent() {
    await this.consentService.setConsentLevel(this.consentLevel);
    // Show confirmation
  }
}
```

---

## Summary

This memory system provides:

✅ **Three-tier architecture** (working → episodic → semantic)
✅ **Four profile levels** (anonymous → registered → active → personalized)
✅ **Google stack integration** (Firestore, Vertex AI embeddings, Gemini)
✅ **Pre-made test profiles** for bootstrapping
✅ **Privacy-first design** with consent management
✅ **Model-agnostic storage** for multi-model evaluation
✅ **Evaluation scenarios** for testing memory accuracy
✅ **Clear migration path** from basic to advanced

### Next Steps

1. **Implement Phase 1** (Firestore storage + test profiles)
2. **Test with Gemini** using your existing API
3. **Add Angular consent UI** for profile level selection
4. **Create memory evaluation scenarios**
5. **Iterate based on evaluation results**

The system is designed to start simple (session-only memory) and progressively add sophistication as you validate each tier. This aligns with your incremental build approach while maintaining the full vision.

---

**Document Version**: 1.0
**Last Updated**: 2026-02-02
**Status**: Design Complete, Implementation Pending
