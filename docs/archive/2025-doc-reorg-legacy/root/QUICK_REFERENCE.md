# AI Library Quick Reference

**Last Updated:** February 3, 2026
**Phase:** 1.5 Complete, Ready for Phase 2

## Service URLs (Docker Compose)

```bash
Catalog Service:      http://localhost:8001
Circulation Service:  http://localhost:8002
ILL Service:          http://localhost:8003
Registry Service:     http://localhost:8004
Agents Service:       http://localhost:8000 (Phase 2)
Redis:                redis://localhost:6379
```

## Key Commands

### Start All Services
```bash
cd "AI Librarian eval/ai-library"
docker-compose up -d
docker-compose ps  # Check status
```

### View Logs
```bash
docker-compose logs -f ill           # ILL service
docker-compose logs -f ill-worker    # Celery worker
docker-compose logs -f redis         # Redis broker
```

### Run Tests
```bash
# All ILL tests (114 total)
docker-compose exec ill uv run pytest services/ill/tests -v

# State machine tests only (40 tests)
docker-compose exec ill uv run pytest services/ill/tests/unit/test_state_transitions.py -v
docker-compose exec ill uv run pytest services/ill/tests/unit/test_state_machine.py -v

# Integration tests (74 tests)
docker-compose exec ill uv run pytest services/ill/tests/integration -v
```

### Rebuild After Code Changes
```bash
docker-compose build ill
docker-compose build ill-worker
docker-compose up -d
```

## Common Workflows

### 1. Create and Approve ILL Request

```bash
# Create outbound request
curl -X POST http://localhost:8003/requests \
  -H "Content-Type: application/json" \
  -d '{
    "book_id": "ext-book-001",
    "patron_id": "patron-001",
    "source_library": "mastodon-institute",
    "priority": "high",
    "patron_justification": "Research for PhD dissertation"
  }'

# Check approval queue
curl http://localhost:8003/queue/pending | jq

# Approve request
curl -X POST http://localhost:8003/requests/{request_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "librarian_id": "staff-001",
    "notes": "Approved for academic research"
  }'
```

### 2. Query Partner Libraries

```bash
# List all libraries
curl http://localhost:8004/libraries | jq

# Get specific library with metrics
curl http://localhost:8004/libraries/mastodon-institute | jq

# Select best library for a book
curl -X POST http://localhost:8004/libraries/select-best \
  -H "Content-Type: application/json" \
  -d '{
    "isbn": "978-0-HANNO-0001",
    "genre": "paleontology"
  }' | jq
```

### 3. Handle Inbound Loan

```bash
# Check inbound approval queue
curl http://localhost:8003/inbound/queue/pending | jq

# Approve inbound loan
curl -X POST http://localhost:8003/inbound/loans/{loan_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "librarian_id": "staff-002",
    "notes": "Partner library has excellent track record"
  }'

# Mark as returned
curl -X POST http://localhost:8003/inbound/item-returned \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "{loan_id}"
  }'
```

## File Navigation

### ILL Service (Primary Development Area)

```
services/ill/src/ill/
├── main.py                   # FastAPI app entry point
├── db.py                     # Database configuration
├── models.py                 # SQLModel database models
├── schemas.py                # Pydantic API schemas
├── routes.py                 # API endpoints
├── state_transitions.py      # State machine transition rules
├── state_machine.py          # StateManager class
├── celery_app.py             # Celery configuration
└── tasks.py                  # Async background tasks

services/ill/tests/
├── unit/
│   ├── test_state_transitions.py    # 27 transition validation tests
│   └── test_state_machine.py        # 13 StateManager tests
└── integration/
    ├── test_outbound_requests.py
    ├── test_inbound_requests.py
    ├── test_lifecycle.py
    └── test_data_isolation.py
```

### Registry Service

```
services/registry/src/registry/
├── main.py           # FastAPI app
├── models.py         # PartnerLibraryModel, LibraryMetricsModel
├── routes.py         # Library selection algorithm
└── schemas.py        # API schemas
```

### Shared Code

```
shared/src/shared/
├── constants.py              # Status enums, constants
├── http_client.py            # call_catalog(), call_circulation(), etc.
└── service_registry.py       # Service URL management
```

### Documentation

```
docs/
├── development/
│   ├── AGENT_INTEGRATION_GUIDE.md    # Phase 2 roadmap (ADK/MCP)
│   ├── DEVELOPMENT_ROADMAP.md
│   └── TDD_OOP_GUIDE.md
├── architecture/
│   ├── SERVICES.md
│   ├── A2A_PROTOCOL.md               # Agent-to-agent spec
│   └── OVERVIEW.md
└── world/
    └── HANNO_WORLD_BIBLE.md

Root Documentation:
├── README.md                          # Project overview
├── PHASE_1.5_COMPLETE.md             # Phase 1.5 summary
└── QUICK_REFERENCE.md                # This file
```

## State Machine Reference

### Outbound Request States
```
PENDING_APPROVAL → APPROVED → REQUESTED → SHIPPED →
RECEIVED → IN_USE → RETURNED → CLOSED
    ↓
  DENIED (terminal)
```

**Side Effects:**
- `RECEIVED → IN_USE`: Triggers `create_circulation_checkout` task

### Inbound Loan States
```
PENDING_APPROVAL → APPROVED → SHIPPED → ACTIVE → RETURNED
    ↓
  DENIED (terminal)
```

**Side Effects:**
- `PENDING_APPROVAL → APPROVED`: Triggers `update_catalog_status(reserve)` task
- `ACTIVE → RETURNED`: Triggers `update_catalog_status(release)` task

## Partner Libraries (Seeded Data)

| Code | Name | Specializations | Fulfillment | Response Time |
|------|------|-----------------|-------------|---------------|
| `mastodon-institute` | The Mastodon Institute | paleontology, ancient-history | 92% | 18.5h |
| `mammoth-valley` | Mammoth Valley Library | local-history, genealogy | 92% | 36h |
| `ivory-university` | Ivory University Library | STEM, engineering | 87% | 24h |
| `tusk-conservatory` | Tusk Conservatory | rare-manuscripts, art | 80% | 48h |

## Celery Tasks

### Registered Tasks
```python
ill.tasks.create_circulation_checkout    # Auto-checkout on receipt
ill.tasks.update_catalog_status          # Reserve/release instances
ill.tasks.notify_partner_library         # A2A notifications (Phase 2)
ill.tasks.check_overdue_ill_items        # Daily overdue check (periodic)
```

### Check Worker Status
```bash
# View worker logs
docker-compose logs -f ill-worker

# Check Redis connection
docker-compose exec redis redis-cli ping

# Monitor queue
docker-compose exec redis redis-cli -n 0 llen celery
```

## Common Issues & Solutions

### Issue: Services won't start
```bash
# Check Docker resources
docker system df

# Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Issue: Tests failing with database errors
```bash
# Reset test database
docker-compose exec ill rm -f /app/db/ill.db
docker-compose restart ill
```

### Issue: Celery tasks not executing
```bash
# Check worker is running
docker-compose ps ill-worker

# Check Redis connection
docker-compose exec ill-worker python -c "from celery_app import app; print(app.broker_connection())"

# Restart worker
docker-compose restart ill-worker
```

### Issue: Import errors after code changes
```bash
# Rebuild with --no-cache
docker-compose build --no-cache ill ill-worker
docker-compose up -d
```

## API Documentation

### Interactive Docs (Swagger UI)
```
ILL Service:        http://localhost:8003/docs
Registry Service:   http://localhost:8004/docs
Catalog Service:    http://localhost:8001/docs
Circulation:        http://localhost:8002/docs
```

### Health Checks
```bash
curl http://localhost:8001/health  # Catalog
curl http://localhost:8002/health  # Circulation
curl http://localhost:8003/health  # ILL
curl http://localhost:8004/health  # Registry
```

## Development Tips

### Watch Mode for Development
```bash
# Run service in watch mode (auto-reload)
cd services/ill
uv run uvicorn ill.main:app --reload --port 8003
```

### Quick Test Cycle
```bash
# Run specific test file
docker-compose exec ill uv run pytest services/ill/tests/unit/test_state_machine.py -v -k "test_valid_outbound"

# Run with print statements visible
docker-compose exec ill uv run pytest services/ill/tests -v -s

# Run with coverage
docker-compose exec ill uv run pytest services/ill/tests --cov=ill --cov-report=term-missing
```

### Database Inspection (SQLite)
```bash
# Copy database locally
docker cp ai-library-ill-1:/app/db/ill.db ./ill_backup.db

# Inspect with SQLite browser or CLI
sqlite3 ill_backup.db "SELECT * FROM ill_audit_trail ORDER BY changed_at DESC LIMIT 10;"
```

## Phase 2 Preparation

### MCP Server Development
See [Agent Integration Guide](docs/development/AGENT_INTEGRATION_GUIDE.md) for:
- MCP server architecture
- Resource and tool specifications
- Agent design patterns
- Implementation roadmap

### Next Steps
1. Create MCP server for ILL service
2. Build ILL Approval Agent with ADK
3. Implement A2A protocol foundation
4. Multi-agent orchestration

## Support & Resources

**Project Documentation:**
- [Phase 1.5 Complete Summary](PHASE_1.5_COMPLETE.md)
- [ILL Service README](services/ill/README.md)
- [Agent Integration Guide](docs/development/AGENT_INTEGRATION_GUIDE.md)

**External Resources:**
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [Celery Documentation](https://docs.celeryq.dev/)
- [Redis Documentation](https://redis.io/docs/)
- [MCP Specification](https://modelcontextprotocol.io/)

---

**Questions?** Check the documentation files listed above or review the test suite for usage examples.
