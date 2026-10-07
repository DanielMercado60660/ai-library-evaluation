## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Service architecture reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: infrastructure-services

> Last verified against code/docs on 2026-02-08. This reference may include implemented and planned content; use Doc Status for interpretation.

# Services Architecture

This document defines the microservices that power each library in the Pachyderm Library Network.

## Service Overview

Each library deployment includes these services:

| Service | Port | Responsibility |
|---------|------|----------------|
| **Catalog** | 8001 | Book metadata, search, availability |
| **Circulation** | 8002 | Checkouts, returns, holds, fines |
| **ILL** | 8003 | Inter-library loan requests |

Network-level services (shared):

| Service | Port | Responsibility |
|---------|------|----------------|
| **Registry** | 8004 | Service discovery, health monitoring, A2A message relay |

---

## Catalog Service (`:8001`)

Manages book metadata and physical copy inventory.

### Endpoints

#### Health Check
```
GET /health
```
Response:
```json
{
  "status": "healthy",
  "service": "catalog",
  "version": "0.1.0"
}
```

#### Search Books
```
GET /books
```
Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search term (matches title, author) |
| `genre` | string | Filter by genre |
| `author` | string | Filter by author name |
| `stratum` | int | Filter by stratum (1-13) |
| `available` | bool | Only return books with available copies |
| `limit` | int | Max results (default: 20, max: 100) |
| `offset` | int | Pagination offset |

Response:
```json
{
  "books": [
    {
      "id": "book-001",
      "title": "Tusk and Sensibility",
      "author": "Elaphine Greymarch",
      "isbn": "978-0-HANNO-0001",
      "genres": ["fiction", "romance", "classics"],
      "stratum": 3,
      "summary": "A tale of love and social expectations in the Grey Court.",
      "publication_year": 1811,
      "total_copies": 3,
      "available_copies": 2
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

#### Get Book Details
```
GET /books/{book_id}
```
Response:
```json
{
  "book": {
    "id": "book-001",
    "title": "Tusk and Sensibility",
    "author": "Elaphine Greymarch",
    "isbn": "978-0-HANNO-0001",
    "genres": ["fiction", "romance", "classics"],
    "stratum": 3,
    "summary": "A tale of love and social expectations in the Grey Court.",
    "publication_year": 1811,
    "publisher": "Grey Hall Publishing",
    "page_count": 352,
    "language": "Common",
    "series": null,
    "series_position": null
  },
  "instances": [
    {
      "id": "inst-001-a",
      "book_id": "book-001",
      "status": "available",
      "location": "shelf-A3",
      "condition": "good",
      "call_number": "FIC GRE 1811"
    },
    {
      "id": "inst-001-b",
      "book_id": "book-001",
      "status": "checked_out",
      "location": null,
      "condition": "good",
      "call_number": "FIC GRE 1811"
    }
  ],
  "total_copies": 2,
  "available_copies": 1
}
```

#### Get Book Instances
```
GET /books/{book_id}/instances
```
Response: Array of `BookInstance` objects.

#### Get Availability Summary
```
GET /books/{book_id}/availability
```
Response:
```json
{
  "book_id": "book-001",
  "total_copies": 3,
  "available": 2,
  "checked_out": 1,
  "on_hold_shelf": 0,
  "in_processing": 0,
  "earliest_return_date": "2026-02-15"
}
```

---

## Circulation Service (`:8002`)

Manages patron accounts, checkouts, returns, holds, and fines.

### Endpoints

#### Health Check
```
GET /health
```

### Patron Management

#### Get Patron
```
GET /patrons/{patron_id}
```
Response:
```json
{
  "id": "patron-001",
  "name": "Trunsworth Greyvale",
  "email": "t.greyvale@greyhall.edu",
  "barcode": "HAN-P-001",
  "category": "adult",
  "checkout_limit": 10,
  "current_checkouts": 3,
  "active_holds": 1,
  "fines_owed": 0.00,
  "blocked": false,
  "registration_date": "2024-01-15",
  "expiration_date": "2027-01-15"
}
```

#### Get Patron Summary
```
GET /patrons/{patron_id}/summary
```
Returns current checkouts, holds, and fines in one call.

### Checkouts

#### Checkout Item
```
POST /checkouts
```
Request:
```json
{
  "instance_id": "inst-001-a",
  "patron_id": "patron-001"
}
```
Response:
```json
{
  "id": "checkout-001",
  "instance_id": "inst-001-a",
  "patron_id": "patron-001",
  "book_title": "Tusk and Sensibility",
  "checked_out_at": "2026-02-02T14:30:00Z",
  "due_date": "2026-02-16T23:59:59Z",
  "renewals_remaining": 2
}
```

Error Cases:
- `400`: Item not available
- `400`: Patron at checkout limit
- `400`: Patron has blocks/excessive fines
- `404`: Instance or patron not found

#### Get Checkout
```
GET /checkouts/{checkout_id}
```

#### List Patron Checkouts
```
GET /patrons/{patron_id}/checkouts
```
Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter: `active`, `returned`, `overdue` |

#### Renew Checkout
```
POST /checkouts/{checkout_id}/renew
```
Response: Updated checkout with new due date.

Error Cases:
- `400`: Max renewals reached
- `400`: Item has holds waiting
- `400`: Item is overdue

#### Return Item
```
POST /returns
```
Request:
```json
{
  "instance_id": "inst-001-a",
  "dropbox": false
}
```
Response:
```json
{
  "checkout_id": "checkout-001",
  "returned_at": "2026-02-10T09:15:00Z",
  "dropbox": false,
  "fines_incurred": 0.00,
  "next_hold_patron": null
}
```

If `dropbox: true`, item enters `DROPBOX` status and requires processing before becoming available.

### Holds

#### Place Hold
```
POST /holds
```
Request:
```json
{
  "book_id": "book-001",
  "patron_id": "patron-001"
}
```
Response:
```json
{
  "id": "hold-001",
  "book_id": "book-001",
  "book_title": "Tusk and Sensibility",
  "patron_id": "patron-001",
  "position": 3,
  "status": "pending",
  "created_at": "2026-02-02T14:30:00Z",
  "estimated_wait": "2-3 weeks"
}
```

#### Get Hold
```
GET /holds/{hold_id}
```

#### List Patron Holds
```
GET /patrons/{patron_id}/holds
```

#### Cancel Hold
```
DELETE /holds/{hold_id}
```

#### Notify Hold Ready
```
POST /holds/{hold_id}/notify
```
Internal endpoint called when item becomes available for next patron in queue.

### Fines

#### List Patron Fines
```
GET /patrons/{patron_id}/fines
```
Response:
```json
{
  "patron_id": "patron-001",
  "total_owed": 2.50,
  "fines": [
    {
      "id": "fine-001",
      "checkout_id": "checkout-042",
      "book_title": "The Fall of Lorde Tuskar",
      "reason": "overdue",
      "amount": 2.50,
      "created_at": "2026-01-20",
      "paid": false
    }
  ]
}
```

#### Pay Fine
```
POST /fines/{fine_id}/pay
```
Request:
```json
{
  "amount": 2.50,
  "method": "cash"
}
```

### Overdue Management

#### List Overdue Items
```
GET /checkouts/overdue
```
Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `days_overdue` | int | Minimum days overdue |
| `limit` | int | Max results |

---

## ILL Service (`:8003`)

Manages inter-library loan requests — both outbound (we're borrowing) and inbound (we're lending).

### Outbound Requests (Borrowing)

#### Create ILL Request
```
POST /requests
```
Request:
```json
{
  "book_id": "book-ext-001",
  "patron_id": "patron-001",
  "source_library": "mastodon-institute",
  "notes": "Needed for research project"
}
```
Response:
```json
{
  "id": "ill-001",
  "book_id": "book-ext-001",
  "book_title": "Principles of Trunk Engineering",
  "patron_id": "patron-001",
  "patron_reference": "HAN-P-001",
  "source_library": "mastodon-institute",
  "status": "requested",
  "created_at": "2026-02-02T14:30:00Z",
  "events": [
    {
      "type": "request_created",
      "timestamp": "2026-02-02T14:30:00Z"
    }
  ]
}
```

#### Get ILL Request
```
GET /requests/{request_id}
```

#### List ILL Requests
```
GET /requests
```
Query Parameters:
| Param | Type | Description |
|-------|------|-------------|
| `status` | string | Filter by status |
| `direction` | string | `outbound` or `inbound` |
| `patron_id` | string | Filter by patron |

#### Mark Item Received
```
POST /requests/{request_id}/receive
```
Called when borrowed item arrives from lending library.

#### Return to Lender
```
POST /requests/{request_id}/return
```
Called when patron returns item; initiates shipping back.

### Inbound Requests (Lending)

These endpoints are called via A2A from other libraries.

#### Query Holdings
```
POST /inbound/query
```
Request (from A2A message):
```json
{
  "isbn": "978-0-HANNO-0001",
  "title": "Tusk and Sensibility"
}
```
Response:
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

**Data Isolation**: This endpoint NEVER returns patron information. Only aggregate availability.

#### Process Loan Request
```
POST /inbound/loan-request
```
Request:
```json
{
  "isbn": "978-0-HANNO-0001",
  "requesting_library": "mastodon-institute",
  "patron_reference": "MAS-P-042"
}
```
Response:
```json
{
  "approved": true,
  "request_id": "ill-inbound-001",
  "estimated_ship_date": "2026-02-04",
  "loan_period_days": 28
}
```

Or denial:
```json
{
  "approved": false,
  "reason": "no_available_copies",
  "earliest_available": "2026-02-15"
}
```

#### Mark Item Returned
```
POST /inbound/item-returned
```
Called when borrowing library ships item back.

---

## Network Services

### Registry Service (`:8004`)

Service discovery, health monitoring, and A2A message relay.

#### Register Library
```
POST /libraries
```
Request:
```json
{
  "library_id": "hanno-memorial",
  "name": "Hanno Memorial Library",
  "base_url": "https://hanno.pachyderm.network",
  "agent_card_url": "https://hanno.pachyderm.network/.well-known/agent.json",
  "capabilities": ["catalog", "circulation", "ill"],
  "status": "online"
}
```

#### List Libraries
```
GET /libraries
```

#### Get Library
```
GET /libraries/{library_id}
```

#### Health Check All
```
GET /health/all
```
Returns health status of all registered libraries.

#### A2A Relay Endpoints

The registry hosts A2A message relay directly (no separate broker service). See [A2A_PROTOCOL.md](./A2A_PROTOCOL.md) for full protocol specification.

#### Send A2A Message
```
POST /a2a/message/send
```

#### Poll A2A Messages
```
GET /a2a/messages/{library_code}
```

#### Acknowledge A2A Message
```
POST /a2a/messages/{message_id}/ack
```

---

## Error Handling

All services use consistent error responses:

```json
{
  "error": {
    "code": "ITEM_NOT_AVAILABLE",
    "message": "The requested item is not available for checkout",
    "details": {
      "instance_id": "inst-001-a",
      "current_status": "checked_out",
      "expected_return": "2026-02-15"
    }
  }
}
```

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `NOT_FOUND` | 404 | Resource doesn't exist |
| `ITEM_NOT_AVAILABLE` | 400 | Item can't be checked out |
| `PATRON_BLOCKED` | 400 | Patron has restrictions |
| `CHECKOUT_LIMIT_REACHED` | 400 | Patron at max checkouts |
| `HOLD_LIMIT_REACHED` | 400 | Patron at max holds |
| `RENEWAL_NOT_ALLOWED` | 400 | Can't renew (overdue, holds waiting, max renewals) |
| `INVALID_REQUEST` | 400 | Malformed request |
| `UNAUTHORIZED` | 401 | Invalid authentication |
| `FORBIDDEN` | 403 | Not permitted |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily down |

---

## Authentication

Services support two authentication modes:

### Internal (Service-to-Service)
```
Authorization: Bearer {service_token}
```
Used for agent-to-service and service-to-service calls within a library.

### Patron Authentication
```
Authorization: Bearer {patron_token}
```
Used for patron-facing endpoints (future: self-checkout kiosk).

### A2A Authentication
See [A2A_PROTOCOL.md](./A2A_PROTOCOL.md) for inter-library authentication.

---

## Database Schema

See [DATA_MODEL.md](./DATA_MODEL.md) for complete entity definitions and relationships.
