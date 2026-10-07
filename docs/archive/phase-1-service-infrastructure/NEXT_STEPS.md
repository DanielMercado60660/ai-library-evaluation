# Next Steps: Functional Library System

**Current Status:** ✅ All three services complete with comprehensive tests

**Immediate Goal:** Get services working together as a functional library system that can be manually tested end-to-end.

## Phase 1: Service Integration (Current Priority)

### What's Needed

#### 1. Cross-Service Communication Pattern

Right now, services have TODO comments for integration:

```python
# In ILL service (routes.py)
# TODO: Integrate with circulation service to verify patron
# TODO: Query catalog service
# TODO: Query external library catalog API
```

**Decision needed:**
- **Option A:** Direct HTTP calls between services
- **Option B:** Shared database (all services read/write same DB)
- **Option C:** Message queue (RabbitMQ, Redis)

**Recommendation:** Start with **Option A** (HTTP) for simplicity, migrate to message queue later if needed.

#### 2. Service Orchestration

Need a way to:
- Start all three services together
- Ensure they can find each other
- Handle service discovery

**Approaches:**
- Docker Compose (services + networking)
- Shell script to start all services
- Simple registry service (service URLs in config file)

#### 3. Integration Testing

Create tests that span multiple services:

```python
# Example: Complete checkout workflow
1. Patron searches catalog (Catalog service)
2. Book is available
3. Patron checks out book (Circulation service)
4. Circulation queries Catalog to reserve instance
5. Circulation creates checkout record
6. Catalog updates instance status to "checked_out"
```

#### 4. Test Data Coordination

Currently each service has its own test fixtures. Need:
- Shared test data (patrons, books, instances)
- Consistent IDs across services
- Database seeding scripts

**File you opened:** `hanno_patrons.json` - good starting point for shared patron data!

### Recommended Implementation Order

#### Step 1: Service Discovery (Simple)

Create `services/shared/src/shared/service_registry.py`:

```python
# Simple service registry - no fancy discovery yet
SERVICE_URLS = {
    "catalog": "http://localhost:8001",
    "circulation": "http://localhost:8002",
    "ill": "http://localhost:8003",
}

def get_service_url(service_name: str) -> str:
    return SERVICE_URLS[service_name]
```

#### Step 2: HTTP Client Helper

Create `services/shared/src/shared/http_client.py`:

```python
import httpx
from typing import Any

async def call_service(
    service: str,
    endpoint: str,
    method: str = "GET",
    data: dict | None = None
) -> Any:
    """Call another service via HTTP."""
    base_url = get_service_url(service)
    url = f"{base_url}{endpoint}"

    async with httpx.AsyncClient() as client:
        if method == "GET":
            response = await client.get(url, params=data)
        elif method == "POST":
            response = await client.post(url, json=data)
        # etc...

        response.raise_for_status()
        return response.json()
```

#### Step 3: Implement Cross-Service Calls

**In ILL Service:**

Replace TODO in `create_ill_request()`:

```python
# Before: Mock patron verification
if request.patron_id == "nonexistent-patron":
    raise HTTPException(status_code=404, detail="Patron not found")

# After: Real patron verification
try:
    patron = await call_service(
        "circulation",
        f"/patrons/{request.patron_id}"
    )
except httpx.HTTPStatusError as e:
    if e.response.status_code == 404:
        raise HTTPException(status_code=404, detail="Patron not found")
    raise
```

**In Circulation Service:**

When checking out a book:

```python
# Query catalog for book availability
book = await call_service(
    "catalog",
    f"/books/{checkout_request.book_id}"
)

# Find available instance
instances = await call_service(
    "catalog",
    f"/books/{checkout_request.book_id}/instances",
    params={"status": "available"}
)

if not instances:
    raise HTTPException(status_code=400, detail="No copies available")

instance = instances[0]

# Reserve the instance
await call_service(
    "catalog",
    f"/instances/{instance['id']}/checkout",
    method="POST",
    data={"checkout_id": checkout.id}
)
```

#### Step 4: Docker Compose Setup

Create `docker-compose.yml` at project root:

```yaml
version: '3.8'

services:
  catalog:
    build: ./services/catalog
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./catalog.db
      - PORT=8001
    volumes:
      - ./data:/app/data

  circulation:
    build: ./services/circulation
    ports:
      - "8002:8002"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./circulation.db
      - PORT=8002
      - CATALOG_SERVICE_URL=http://catalog:8001
    depends_on:
      - catalog

  ill:
    build: ./services/ill
    ports:
      - "8003:8003"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///./ill.db
      - PORT=8003
      - CATALOG_SERVICE_URL=http://catalog:8001
      - CIRCULATION_SERVICE_URL=http://circulation:8002
    depends_on:
      - catalog
      - circulation
```

#### Step 5: Manual Testing Scripts

Create `scripts/test_workflows.py`:

```python
#!/usr/bin/env python3
"""
Manual testing script for complete library workflows.
Traces the flow through all services.
"""

import asyncio
import httpx

async def test_complete_checkout_workflow():
    """Test: Patron searches, finds book, checks it out."""
    print("=== Complete Checkout Workflow ===\n")

    # Step 1: Search for book
    print("1. Searching for 'Pachyderm Algorithms'...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://localhost:8001/books",
            params={"title": "Pachyderm"}
        )
        books = response.json()
        print(f"   Found {len(books)} books")
        book_id = books[0]["id"]

    # Step 2: Check availability
    print(f"2. Checking availability for book {book_id}...")
    # ... etc

    # Step 3: Checkout
    print("3. Creating checkout...")
    # ...

    print("\n✅ Checkout workflow complete!")

async def test_ill_workflow():
    """Test: Patron requests external book via ILL."""
    print("=== ILL Request Workflow ===\n")
    # ...

if __name__ == "__main__":
    asyncio.run(test_complete_checkout_workflow())
    asyncio.run(test_ill_workflow())
```

#### Step 6: Integration Tests

Create `tests/integration/test_cross_service.py`:

```python
"""
Cross-service integration tests.
These tests require all services to be running.
"""

import pytest
from httpx import AsyncClient

@pytest.mark.integration
@pytest.mark.asyncio
async def test_checkout_updates_catalog():
    """Verify that checkout updates catalog instance status."""
    # Create checkout in Circulation
    # Verify instance status changed in Catalog
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_ill_verifies_patron():
    """Verify ILL service queries Circulation for patron verification."""
    # Create ILL request with valid patron
    # Verify Circulation was queried
    # Create ILL request with invalid patron
    # Verify proper error
    pass
```

### Testing Strategy

**Local development:**
```bash
# Terminal 1
cd services/catalog && uvicorn catalog.main:app --port 8001

# Terminal 2
cd services/circulation && uvicorn circulation.main:app --port 8002

# Terminal 3
cd services/ill && uvicorn ill.main:app --port 8003

# Terminal 4
python scripts/test_workflows.py
```

**With Docker:**
```bash
docker-compose up
python scripts/test_workflows.py
```

### Current Blockers / Questions

1. **Database strategy:**
   - Each service separate DB? (current)
   - Shared database?
   - How to handle test data across services?

2. **Service URLs:**
   - Hardcode in config?
   - Environment variables?
   - Service discovery mechanism?

3. **Error handling:**
   - What happens if Catalog service is down when Circulation tries to query it?
   - Retry logic?
   - Circuit breakers?

4. **Transaction consistency:**
   - If checkout succeeds but catalog update fails, what happens?
   - Need distributed transactions?
   - Saga pattern?

## Decision Points

Before proceeding, need to decide:

### 1. Integration Pattern
- [ ] Direct HTTP calls (simple, start here)
- [ ] Shared database (simpler but less realistic)
- [ ] Message queue (more complex, better for production)

### 2. Service Discovery
- [ ] Hardcoded URLs in config (simplest)
- [ ] Environment variables (Docker-friendly)
- [ ] Service registry (most flexible)

### 3. Data Strategy
- [ ] Each service owns its data (current)
- [ ] Shared patron/book data (denormalized)
- [ ] Event sourcing (complex but powerful)

### 4. Development Environment
- [ ] Manual (run 3 terminals)
- [ ] Docker Compose (containerized)
- [ ] Both (Docker for integration tests, manual for dev)

## Recommended Next Actions

**If you want to move fast and manually test:**

1. Create simple service registry in shared package
2. Add HTTP client helper to shared package
3. Implement 1-2 critical cross-service calls (e.g., ILL → Circulation patron check)
4. Create manual test script
5. Run all three services locally and trace a complete workflow

**If you want proper infrastructure first:**

1. Set up Docker Compose
2. Create database seeding scripts with shared test data
3. Build integration test framework
4. Then implement cross-service calls

**My recommendation:** Hybrid approach
1. Simple service registry + HTTP client (1 hour)
2. Implement key integration points (2-3 hours)
3. Manual test script (1 hour)
4. Trace 2-3 complete workflows manually
5. Once working, add Docker Compose and proper tests

## What do you want to tackle first?

Given where you are and your goals:

**Option A:** Start with cross-service integration (HTTP calls)
- Quick wins, see services talking
- Can manually test complete workflows
- Build confidence in architecture

**Option B:** Set up proper infrastructure first (Docker Compose, shared data)
- More upfront work
- Better foundation
- Easier to automate testing

**Option C:** Hybrid - simple integration + manual testing
- Implement 1-2 key integration points
- Create test script to trace flows
- See it working end-to-end
- Then add infrastructure

Which direction resonates with you?
