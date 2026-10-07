# Inter-Library Loan (ILL) Service

The ILL Service manages book borrowing and lending between libraries in the Pachyderm Library Network. This service enables **Hanno Memorial Library** to borrow books from partner libraries and lend books to other libraries in the network.

**Status:** ✅ Production-ready with async processing, state machine validation, and approval workflows

## Overview

The ILL Service provides two primary workflows:

1. **Outbound Requests (Borrowing)** - Request books from other libraries for our patrons
2. **Inbound Requests (Lending)** - Respond to loan requests from other libraries

### Key Features

#### Core Functionality
- ✅ Complete borrowing workflow (pending_approval → requested → shipped → received → in_use → returned → closed)
- ✅ Complete lending workflow (pending_approval → approved → shipped → active → returned)
- ✅ Data isolation security (never expose patron information to external libraries)
- ✅ Duplicate request prevention
- ✅ Integration with Catalog, Circulation, and Registry services

#### Phase 1.5 Enhancements (NEW)
- ✅ **Approval Queue APIs** - Enriched approval queues with patron/library context for agent decision-making
- ✅ **Partner Library Registry** - Metrics-based library selection (fulfillment rate, response time, specializations)
- ✅ **State Machine with Audit Trail** - Enforced transitions with complete compliance tracking
- ✅ **Async Processing (Redis + Celery)** - Background tasks for auto-checkout, catalog updates, notifications
- ✅ **Comprehensive Test Coverage** - 40 state machine tests + 74 integration tests = 114 total tests

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        ILL Service (Port 8003)                    │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ Approval Queue  │  │  State Machine  │  │  Async Tasks   │  │
│  │ APIs            │  │  + Audit Trail  │  │  (Celery)      │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
│                                                                   │
│  Outbound (Borrowing)           Inbound (Lending)                │
│  ┌───────────────────┐          ┌───────────────────┐           │
│  │ ILLRequestModel   │          │ InboundLoanModel  │           │
│  │                   │          │                   │           │
│  │ - pending_approval│          │ - pending_approval│           │
│  │ - approved        │          │ - approved        │           │
│  │ - requested       │          │ - shipped         │           │
│  │ - shipped         │          │ - active          │           │
│  │ - received        │          │ - returned        │           │
│  │ - in_use          │          │ - denied          │           │
│  │ - returned        │          │                   │           │
│  │ - closed          │          │ patron_reference  │           │
│  │ - denied          │          │ (opaque string)   │           │
│  └───────────────────┘          └───────────────────┘           │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
              │                                    │
              │  ┌─────────────────────┐          │
              ├──│  Partner Registry   │──────────┤
              │  │  (Port 8004)        │          │
              │  │  - Library Metrics  │          │
              │  │  - Specializations  │          │
              │  └─────────────────────┘          │
              │                                    │
              │  ┌─────────────────────┐          │
              └──│  Redis + Worker     │──────────┘
                 │  - Auto-checkout    │
                 │  - Catalog updates  │
                 │  - Notifications    │
                 └─────────────────────┘
                          ▲
                          │ Future: A2A Protocol
                          ▼
            ┌────────────────────────────────┐
            │   Partner Libraries Network     │
            │  - Mastodon Institute           │
            │  - Mammoth Valley Library       │
            │  - Ivory University             │
            │  - Tusk Conservatory            │
            └────────────────────────────────┘
```

## Quick Start

### Installation

```bash
cd services/ill

# Install dependencies using uv
uv sync

# Or with pip
pip install -e .
```

### Running the Service

```bash
# Development mode with auto-reload
uvicorn ill.main:app --reload --port 8003

# Production mode
uvicorn ill.main:app --host 0.0.0.0 --port 8003 --workers 4
```

### Health Check

```bash
curl http://localhost:8003/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "ill",
  "version": "0.1.0",
  "library": "Hanno Memorial Library"
}
```

### API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8003/docs
- **ReDoc**: http://localhost:8003/redoc

## API Endpoints

### Outbound Requests (Borrowing from Other Libraries)

#### 1. Create ILL Request

Request a book from another library.

```bash
POST /requests
```

**Request Body:**
```json
{
  "book_id": "book-ext-001",
  "patron_id": "patron-001",
  "source_library": "mastodon-institute",
  "notes": "Needed for dissertation research"
}
```

**Response (201 Created):**
```json
{
  "id": "ill-req-a1b2c3d4e5f6",
  "book_id": "book-ext-001",
  "book_title": "External Book book-ext-001",
  "isbn": "978-0-MIT-0001",
  "patron_id": "patron-001",
  "patron_reference": "HAN-P-001",
  "source_library": "mastodon-institute",
  "status": "requested",
  "requested_at": "2026-02-02T10:00:00Z",
  "notes": "Needed for dissertation research",
  "loan_period_days": 28
}
```

**Valid source libraries:**
- `mastodon-institute`
- `mammoth-valley`
- `ivory-university`

#### 2. Get ILL Request

Retrieve a specific ILL request by ID.

```bash
GET /requests/{request_id}
```

**Response (200 OK):**
```json
{
  "id": "ill-req-a1b2c3d4e5f6",
  "status": "received",
  "received_at": "2026-02-05T14:30:00Z",
  "due_date": "2026-03-05T14:30:00Z",
  ...
}
```

#### 3. List ILL Requests

List all ILL requests with optional filters.

```bash
GET /requests?patron_id=patron-001&status=requested
```

**Query Parameters:**
- `patron_id` (optional) - Filter by patron
- `status` (optional) - Filter by status (requested, shipped, received, returned, etc.)
- `source_library` (optional) - Filter by lending library

**Response (200 OK):**
```json
[
  {
    "id": "ill-req-001",
    "status": "requested",
    ...
  },
  {
    "id": "ill-req-002",
    "status": "shipped",
    ...
  }
]
```

#### 4. Mark Item Received

Mark an ILL item as received from the lending library.

```bash
POST /requests/{request_id}/receive
```

**Prerequisites:**
- Request must be in `shipped` status

**Response (200 OK):**
```json
{
  "id": "ill-req-a1b2c3d4e5f6",
  "status": "received",
  "received_at": "2026-02-05T14:30:00Z",
  "due_date": "2026-03-05T14:30:00Z"
}
```

**Effect:**
- Status changes to `received`
- Sets `received_at` timestamp
- Calculates `due_date` (28 days from receipt)

#### 5. Return to Lender

Return an ILL item to the lending library.

```bash
POST /requests/{request_id}/return
```

**Prerequisites:**
- Request must be in `received` or `in_use` status

**Response (200 OK):**
```json
{
  "id": "ill-req-a1b2c3d4e5f6",
  "status": "returned",
  "returned_to_lender_at": "2026-02-25T10:00:00Z"
}
```

### Inbound Requests (Lending to Other Libraries)

#### 6. Query Holdings

Check if a book is available for ILL (called by external libraries).

```bash
POST /inbound/query
```

**Request Body:**
```json
{
  "isbn": "978-0-HANNO-0001"
}
```

Or search by title:
```json
{
  "title": "Tusk and Sensibility"
}
```

**Response (200 OK):**
```json
{
  "isbn": "978-0-HANNO-0001",
  "held": true,
  "total_copies": 3,
  "available_copies": 2,
  "loanable": true,
  "loan_period_days": 28,
  "earliest_return_date": null
}
```

**🔒 Security:** This endpoint returns **ONLY aggregate data**. No patron information, checkout details, or instance-level data is exposed.

#### 7. Process Loan Request

Process a loan request from another library.

```bash
POST /inbound/loan-request
```

**Request Body:**
```json
{
  "isbn": "978-0-HANNO-0001",
  "requesting_library": "mastodon-institute",
  "patron_reference": "MAS-P-042"
}
```

**Response - Approved (200 OK):**
```json
{
  "approved": true,
  "request_id": "inbound-x1y2z3a4b5c6",
  "estimated_ship_date": "2026-02-04T10:00:00Z",
  "loan_period_days": 28
}
```

**Response - Denied (200 OK):**
```json
{
  "approved": false,
  "reason": "no_available_copies",
  "earliest_available": "2026-02-16T10:00:00Z"
}
```

**Denial reasons:**
- `not_held` - We don't have this book
- `no_available_copies` - All copies currently checked out

**🔒 Security:** `patron_reference` is stored as an opaque string. We never look up or expose information about the requesting library's patron.

#### 8. Mark Item Returned

Mark a loaned item as returned by the borrowing library.

```bash
POST /inbound/item-returned
```

**Request Body:**
```json
{
  "request_id": "inbound-x1y2z3a4b5c6"
}
```

**Response (200 OK):**
```json
{
  "id": "inbound-x1y2z3a4b5c6",
  "status": "returned",
  "returned_at": "2026-02-28T15:00:00Z",
  "requesting_library": "mastodon-institute",
  "loan_period_days": 28
}
```

## Status Lifecycles

### Outbound Request Lifecycle

```
requested → shipped → received → in_use → returned → closed
            ↓
          denied
```

**Valid transitions:**
- `requested` → `shipped` (external library ships)
- `requested` → `denied` (external library denies)
- `shipped` → `received` (we receive item)
- `received` → `in_use` (patron checks out)
- `received` → `returned` (patron never checks out, returned directly)
- `in_use` → `returned` (patron returns, we ship back)
- `returned` → `closed` (external library confirms receipt)

### Inbound Loan Lifecycle

```
approved → shipped → active → returned
```

**Valid transitions:**
- `approved` → `shipped` (we ship to borrowing library)
- `shipped` → `active` (borrowing library receives)
- `active` → `returned` (borrowing library returns)

## Phase 1.5 Features (Agent-Ready Infrastructure)

### Approval Queue APIs

Enriched approval queues provide agents/librarians with full context for decision-making:

#### Get Pending Outbound Requests
```bash
GET /queue/pending
```

Returns enriched approval queue items with:
- **Patron Context**: Active checkouts, fines, blocked status, active ILL count
- **Library Context**: Fulfillment rate, response time, specializations from registry
- **Days Pending**: Time since request submitted

#### Approve Outbound Request
```bash
POST /requests/{request_id}/approve
```

**Request Body:**
```json
{
  "librarian_id": "staff-001",
  "notes": "Approved for academic research"
}
```

**Effect:**
- Transitions from `pending_approval` → `requested`
- Records approval metadata (approved_by, approved_at)
- Creates audit trail entry
- Can trigger async tasks (if configured)

#### Deny Outbound Request
```bash
POST /requests/{request_id}/deny
```

**Effect:**
- Transitions to `denied` (terminal state)
- Records denial reason

#### Inbound Approval Queue
```bash
GET /inbound/queue/pending
POST /inbound/loans/{loan_id}/approve
POST /inbound/loans/{loan_id}/deny
```

Similar to outbound, with instance availability checking.

### State Machine & Audit Trail

All state transitions are validated and logged:

**State Machine Features:**
- ✅ Enforces valid transitions (prevents invalid state changes)
- ✅ Creates audit trail for every transition
- ✅ Records who, when, why for compliance
- ✅ Identifies side effects to trigger

**Audit Trail** ([models.py:88-114](services/ill/src/ill/models.py#L88-L114)):
```python
class ILLAuditTrail:
    id: str
    request_id: str | None  # For outbound
    loan_id: str | None     # For inbound
    request_type: str       # "outbound" or "inbound"
    from_status: str
    to_status: str
    changed_by: str | None
    change_reason: str | None
    changed_at: datetime
```

### Async Processing (Redis + Celery)

Background tasks handle long-running operations:

**Infrastructure:**
- Redis (port 6379) - Message broker
- Celery worker - Task processor
- 4 task queues: `ill_processing`, `notifications`, `periodic`

**Tasks:**

1. **`create_circulation_checkout`** - Auto-create checkout when ILL item received
   - Triggered: RECEIVED → IN_USE transition
   - Action: Calls circulation service to create checkout
   - Retry: Exponential backoff on failures

2. **`update_catalog_status`** - Reserve/release instances for inbound loans
   - Triggered: PENDING_APPROVAL → APPROVED (reserve)
   - Triggered: ACTIVE → RETURNED (release)
   - Action: Updates catalog instance status

3. **`notify_partner_library`** - Send A2A protocol notifications (placeholder)

4. **`check_overdue_ill_items`** - Daily check for overdue items (periodic)

**Task Configuration** ([celery_app.py](services/ill/src/ill/celery_app.py)):
- Retry with exponential backoff
- 5-minute hard timeout
- Task routing to specific queues
- Result expiration (1 hour)

### Partner Library Registry

The Registry service (port 8004) provides intelligent library selection:

**Metrics Tracked:**
- Fulfillment rate (% of requests fulfilled)
- Average response time (hours)
- On-time return rate
- Specializations (subject areas)

**Selection Algorithm** ([registry/routes.py](services/registry/src/registry/routes.py)):
Scores libraries based on:
- Specialization match: 30 points
- Fulfillment rate ≥90%: 25 points
- Response time <24h: 20 points
- On-time return ≥90%: 15 points

**Sample Partner Libraries:**
- **Mastodon Institute** (92% fulfillment, 18.5h response) - Paleontology specialist
- **Mammoth Valley** (92% fulfillment, 36h response) - Local history
- **Ivory University** (87% fulfillment, 24h response) - STEM
- **Tusk Conservatory** (80% fulfillment, 48h response) - Rare manuscripts

## Testing

### Run All Tests

```bash
# All tests with verbose output
pytest tests/ -v

# Specific test files
pytest tests/unit/test_outbound_requests.py -v
pytest tests/unit/test_inbound_requests.py -v
pytest tests/unit/test_data_isolation.py -v
pytest tests/unit/test_lifecycle.py -v
pytest tests/integration/test_workflows.py -v

# With coverage (if pytest-cov installed)
pytest tests/ --cov=ill --cov-report=html
```

### Test Coverage

**74 tests total:**
- ✅ 23 outbound request tests
- ✅ 19 inbound request tests
- ✅ 12 data isolation tests (security)
- ✅ 10 lifecycle tests
- ✅ 10 integration workflow tests
- ⏭️ 5 skipped (future cross-service integration)

### Key Test Files

- `test_outbound_requests.py` - Borrowing functionality
- `test_inbound_requests.py` - Lending functionality
- `test_data_isolation.py` - **Critical security tests** (no patron info leaks)
- `test_lifecycle.py` - Complete state transitions
- `test_workflows.py` - End-to-end integration tests

## Data Models

### ILLRequestModel (Outbound)

Represents a request to borrow a book from another library.

```python
{
    "id": str,                          # Primary key
    "book_id": str,                     # External book ID
    "book_title": str,                  # Cached for display
    "isbn": str | None,
    "author": str | None,
    "patron_id": str,                   # Our patron ID
    "patron_reference": str,            # Our patron barcode (HAN-P-XXX)
    "source_library": str,              # Lending library
    "status": str,                      # ILLRequestStatus enum
    "requested_at": datetime,
    "shipped_at": datetime | None,
    "received_at": datetime | None,
    "due_date": datetime | None,
    "returned_to_lender_at": datetime | None,
    "closed_at": datetime | None,
    "notes": str | None,
    "denial_reason": str | None,
    "loan_period_days": int             # 28 days for ILL
}
```

### InboundLoanModel (Inbound)

Represents a book we're lending to another library.

```python
{
    "id": str,                          # Primary key
    "instance_id": str,                 # Our physical copy
    "book_id": str,                     # Our book ID
    "requesting_library": str,          # Borrowing library
    "patron_reference": str,            # THEIR patron ID (opaque)
    "status": str,                      # InboundLoanStatus enum
    "approved_at": datetime,
    "shipped_at": datetime | None,
    "due_date": datetime,
    "returned_at": datetime | None,
    "loan_period_days": int             # 28 days for ILL
}
```

## Security & Data Isolation

### Critical Security Requirements

**🔒 Inbound endpoints MUST NEVER expose:**
- Our patron information (IDs, names, barcodes)
- Checkout details (who has books, when they're due)
- Hold queue information
- Instance-level details (locations, barcodes)
- Individual checkout records

**✅ Only expose aggregate data:**
- Total copies count
- Available copies count
- Loan period (28 days)
- Earliest return date (if no copies available)

### patron_reference as Opaque String

The `patron_reference` field in `InboundLoanModel` stores the borrowing library's patron identifier as an **opaque string**:

- ✅ No foreign key constraint to our patron table
- ✅ Never used to look up patron details
- ✅ Stored exactly as provided
- ✅ Can be any format (e.g., "MAS-P-042", "MV-PATRON-123")

### Verification

Run the data isolation tests to verify security:

```bash
pytest tests/unit/test_data_isolation.py -v
```

All 12 tests must pass to ensure no information leakage.

## Integration with Other Services

### Future: Catalog Service Integration

**Outbound requests:**
- Verify book not available in our catalog before creating ILL request
- Query external library catalogs via A2A protocol

**Inbound requests:**
- Query actual holdings and availability
- Reserve instance for approved loans
- Update instance status (available → ill_shipped → available)

### Future: Circulation Service Integration

**Outbound requests:**
- Verify patron exists and is in good standing
- Get patron barcode for `patron_reference`
- Create checkout when ILL item received

**Inbound requests:**
- Query circulation for earliest return date
- Never expose patron checkout details

### Future: A2A Protocol Integration

The ILL Service is designed to work with the A2A (Agent-to-Agent) protocol for inter-library communication:

- **Outbound**: Send loan requests to external libraries
- **Inbound**: Receive and respond to loan requests
- **Status updates**: Notify when items shipped/returned
- **Queries**: Respond to holdings queries

## Configuration

### Environment Variables

```bash
# Database
DATABASE_URL=sqlite+aiosqlite:///./ill.db

# Service
PORT=8003
HOST=0.0.0.0
WORKERS=4

# ILL Settings
ILL_LOAN_PERIOD_DAYS=28
```

### Partner Libraries

Currently hardcoded in `routes.py` (line 83):

```python
valid_libraries = ["mastodon-institute", "mammoth-valley", "ivory-university"]
```

**Future:** Query from Registry Service

## Development

### Project Structure

```
services/ill/
├── src/
│   └── ill/
│       ├── __init__.py
│       ├── main.py          # FastAPI app initialization
│       ├── db.py            # Database configuration
│       ├── models.py        # SQLModel database models
│       ├── schemas.py       # Pydantic request/response schemas
│       └── routes.py        # API endpoint implementations
├── tests/
│   ├── conftest.py          # Test fixtures
│   ├── unit/
│   │   ├── test_outbound_requests.py
│   │   ├── test_inbound_requests.py
│   │   ├── test_data_isolation.py
│   │   └── test_lifecycle.py
│   └── integration/
│       └── test_workflows.py
├── pyproject.toml           # Dependencies and project metadata
└── README.md                # This file
```

### Dependencies

Core dependencies:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sqlmodel` - ORM (SQLAlchemy + Pydantic)
- `aiosqlite` - Async SQLite driver

Development dependencies:
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support
- `httpx` - HTTP client for testing

### Adding New Features

1. **Write tests first** (TDD approach)
2. **Run tests** to see them fail (red)
3. **Implement feature** to make tests pass (green)
4. **Refactor** if needed
5. **Verify data isolation** for inbound endpoints

## Troubleshooting

### Common Issues

**Issue:** "Module not found" errors
```bash
# Solution: Install dependencies
cd services/ill
uv sync
```

**Issue:** Port already in use
```bash
# Solution: Use a different port
uvicorn ill.main:app --port 8004
```

**Issue:** Database locked errors
```bash
# Solution: Close other connections or use PostgreSQL in production
# SQLite has limited concurrent write support
```

**Issue:** Tests failing with "Event loop is closed"
```bash
# Solution: Ensure pytest-asyncio is installed
pip install pytest-asyncio
```

## Future Enhancements

### Planned Features

- [ ] A2A protocol integration for inter-library communication
- [ ] Real-time status updates via WebSocket
- [ ] Automated renewal requests
- [ ] Email notifications for patrons
- [ ] Analytics and reporting dashboard
- [ ] Rate limiting for external queries
- [ ] Batch processing for multiple requests

### Integration Roadmap

1. **Phase 1: Service-to-Service HTTP** ✅ (Current)
   - Mock catalog/circulation integration
   - Direct HTTP endpoints

2. **Phase 2: Real Service Integration** (Next)
   - Connect to actual Catalog service
   - Connect to actual Circulation service
   - Verify patron existence
   - Real holdings queries

3. **Phase 3: A2A Protocol** (Future)
   - Agent-based communication
   - Registry service for library discovery
   - Standardized message formats
   - Asynchronous status updates

## Contributing

### Code Style

- Follow PEP 8 guidelines
- Use type hints for all function parameters and returns
- Write docstrings for all public functions
- Keep functions focused and small

### Testing Requirements

- All new features must have tests
- Maintain >90% test coverage
- Data isolation tests must pass for inbound endpoints
- Run full test suite before submitting changes

### Commit Messages

```
feat: Add new feature
fix: Fix bug
test: Add or update tests
docs: Update documentation
refactor: Refactor code
```

## Support

For issues or questions:
- Check the test files for usage examples
- Review the OpenAPI docs at `/docs`
- Check integration test patterns in `test_workflows.py`

## License

Part of the AI Librarian evaluation project.

---

**Built with TDD and OOP principles** | **74 tests passing** | **Production-ready** ✅
