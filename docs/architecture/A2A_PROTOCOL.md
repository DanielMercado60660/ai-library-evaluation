## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: A2A protocol reference
- Source of Truth: docs/status/PROJECT_STATUS.md
- Supersedes: N/A
- Related Workstream: a2a-network

> Last verified against code/docs on 2026-02-09. MVP relay semantics are implemented and tested; full JSON-RPC protocol features are deferred.

# A2A Protocol Implementation

This document describes how libraries in the Pachyderm Network communicate using the Agent-to-Agent (A2A) protocol.

## Overview

A2A enables library agents to collaborate without exposing internal implementations. Hanno Memorial doesn't need to know how Mastodon Institute's catalog works — only that it can answer "do you have this book?"

### Why A2A?

| Capability | Without A2A | With A2A |
|------------|-------------|----------|
| Cross-library search | Direct DB access (security risk) | Query via message |
| ILL requests | Manual process | Automated negotiation |
| Holdings sync | Batch exports | Real-time queries |
| Privacy | Data leakage risk | Opaque references |

### Protocol Choice

A2A supports multiple bindings. We use **JSON-RPC 2.0 over HTTPS** because:
- Firewall-friendly (standard HTTPS)
- Wide language support
- Easy debugging (JSON is human-readable)
- Matches official A2A recommendation for new implementations

gRPC is available for high-performance scenarios but not required for library-scale traffic.

---

## Agent Cards

Every library publishes an Agent Card at `/.well-known/agent.json` describing its capabilities.

### Hanno Memorial Agent Card

```json
{
  "name": "Hanno Memorial Library",
  "description": "A humanities-focused library specializing in elephant-themed literature",
  "url": "https://hanno.pachyderm.network",
  "version": "0.1.0",
  
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  
  "skills": [
    {
      "id": "catalog-search",
      "name": "Catalog Search",
      "description": "Search our collection of elephant-themed literature",
      "tags": ["catalog", "search", "books"]
    },
    {
      "id": "holdings-query",
      "name": "Holdings Query",
      "description": "Check if we hold a specific book and its availability",
      "tags": ["ill", "holdings", "availability"]
    },
    {
      "id": "loan-request",
      "name": "ILL Loan Request",
      "description": "Request to borrow a book for inter-library loan",
      "tags": ["ill", "loan", "borrow"]
    }
  ],
  
  "defaultInputModes": ["text"],
  "defaultOutputModes": ["text"],
  
  "authentication": {
    "schemes": ["bearer"]
  },
  
  "provider": {
    "organization": "Pachyderm Library Network",
    "url": "https://pachyderm.network"
  }
}
```

### Mastodon Institute Agent Card

```json
{
  "name": "Mastodon Institute of Technology Library",
  "description": "A research library focused on STEM and technical subjects",
  "url": "https://mastodon.pachyderm.network",
  "version": "0.1.0",
  
  "capabilities": {
    "streaming": false,
    "pushNotifications": false,
    "stateTransitionHistory": true
  },
  
  "skills": [
    {
      "id": "catalog-search",
      "name": "Catalog Search",
      "description": "Search our technical and scientific collection",
      "tags": ["catalog", "search", "books", "technical"]
    },
    {
      "id": "holdings-query",
      "name": "Holdings Query",
      "description": "Check holdings and availability",
      "tags": ["ill", "holdings"]
    },
    {
      "id": "loan-request",
      "name": "ILL Loan Request",
      "description": "Request to borrow materials",
      "tags": ["ill", "loan"]
    }
  ],
  
  "authentication": {
    "schemes": ["bearer"]
  }
}
```

---

## Message Types

### Core Message Envelope

All A2A messages follow this structure:

```python
class A2AMessage(BaseModel):
    """A2A message envelope."""
    
    id: str                        # Unique message ID (UUID)
    type: A2AMessageType           # Message type enum
    from_library: str              # Sender library ID
    to_library: str                # Recipient library ID
    correlation_id: str | None     # Links related messages
    timestamp: datetime            # ISO 8601 timestamp
    payload: dict                  # Type-specific data
```

### Message Type Enum

```python
class A2AMessageType(str, Enum):
    """Types of A2A messages."""
    
    # Discovery
    HOLDINGS_QUERY = "holdings_query"
    HOLDINGS_RESPONSE = "holdings_response"
    
    # ILL Request Lifecycle
    LOAN_REQUEST = "loan_request"
    LOAN_APPROVED = "loan_approved"
    LOAN_DENIED = "loan_denied"
    
    # Fulfillment
    ITEM_SHIPPED = "item_shipped"
    ITEM_RECEIVED = "item_received"
    ITEM_RETURNED = "item_returned"
    ITEM_RECEIVED_BACK = "item_received_back"
    
    # Errors
    REQUEST_FAILED = "request_failed"
    UNAUTHORIZED = "unauthorized"
```

---

## Message Flows

### 1. Holdings Query

Check if another library has a book.

```
┌─────────┐                                      ┌─────────┐
│  HANNO  │                                      │MASTODON │
│   ILL   │                                      │   ILL   │
│  AGENT  │                                      │  AGENT  │
└────┬────┘                                      └────┬────┘
     │                                                │
     │  HOLDINGS_QUERY                                │
     │  {isbn: "978-0-MAST-0042",                     │
     │   title: "Principles of Trunk Engineering"}    │
     │ ─────────────────────────────────────────────► │
     │                                                │
     │                                                │ (queries local catalog)
     │                                                │
     │  HOLDINGS_RESPONSE                             │
     │  {isbn: "978-0-MAST-0042",                     │
     │   held: true,                                  │
     │   total_copies: 2,                             │
     │   available_copies: 1,                         │
     │   loanable: true}                              │
     │ ◄───────────────────────────────────────────── │
     │                                                │
```

#### Holdings Query Payload

```json
{
  "isbn": "978-0-MAST-0042",
  "title": "Principles of Trunk Engineering"
}
```

#### Holdings Response Payload

```json
{
  "isbn": "978-0-MAST-0042",
  "held": true,
  "total_copies": 2,
  "available_copies": 1,
  "loanable": true,
  "loan_period_days": 28,
  "earliest_return_date": null,
  "restrictions": []
}
```

Or if not held:

```json
{
  "isbn": "978-0-MAST-0042",
  "held": false
}
```

---

### 2. ILL Request Flow

Full inter-library loan lifecycle.

```
┌─────────┐                                      ┌─────────┐
│  HANNO  │                                      │MASTODON │
└────┬────┘                                      └────┬────┘
     │                                                │
     │  LOAN_REQUEST                                  │
     │  {isbn: "978-0-MAST-0042",                     │
     │   patron_reference: "HAN-P-042",               │
     │   requested_loan_days: 28}                     │
     │ ─────────────────────────────────────────────► │
     │                                                │
     │  LOAN_APPROVED                                 │
     │  {request_id: "ILL-MAS-001",                   │
     │   approved: true,                              │
     │   loan_period_days: 28,                        │
     │   estimated_ship_date: "2026-02-04"}           │
     │ ◄───────────────────────────────────────────── │
     │                                                │
     │  ITEM_SHIPPED                                  │
     │  {request_id: "ILL-MAS-001",                   │
     │   tracking: "PKG-12345",                       │
     │   estimated_arrival: "2026-02-06"}             │
     │ ◄───────────────────────────────────────────── │
     │                                                │
     │  ITEM_RECEIVED                                 │
     │  {request_id: "ILL-MAS-001",                   │
     │   received_at: "2026-02-06T10:30:00Z"}         │
     │ ─────────────────────────────────────────────► │
     │                                                │
     │           ... patron uses book ...             │
     │                                                │
     │  ITEM_RETURNED                                 │
     │  {request_id: "ILL-MAS-001",                   │
     │   return_tracking: "PKG-12346"}                │
     │ ─────────────────────────────────────────────► │
     │                                                │
     │  ITEM_RECEIVED_BACK                            │
     │  {request_id: "ILL-MAS-001",                   │
     │   condition: "good",                           │
     │   request_complete: true}                      │
     │ ◄───────────────────────────────────────────── │
     │                                                │
```

#### Loan Request Payload

```json
{
  "isbn": "978-0-MAST-0042",
  "patron_reference": "HAN-P-042",
  "requested_loan_days": 28,
  "notes": "Needed for research project"
}
```

**CRITICAL**: `patron_reference` is an opaque identifier. It does NOT contain:
- Patron name
- Patron email
- Patron address
- Checkout history
- Fine information

The lending library (Mastodon) only knows that Hanno is requesting the book for some patron they identify as "HAN-P-042".

#### Loan Approved Payload

```json
{
  "request_id": "ILL-MAS-001",
  "approved": true,
  "loan_period_days": 28,
  "due_date": "2026-03-06",
  "estimated_ship_date": "2026-02-04",
  "conditions": []
}
```

#### Loan Denied Payload

```json
{
  "request_id": "ILL-MAS-001",
  "approved": false,
  "reason": "no_available_copies",
  "details": "All copies currently checked out",
  "earliest_available": "2026-02-20",
  "alternatives": [
    {
      "library_id": "mammoth-valley",
      "has_available": true
    }
  ]
}
```

---

## JSON-RPC Binding

A2A uses JSON-RPC 2.0. Here's how messages map:

### Sending a Message

```http
POST /a2a/rpc HTTP/1.1
Host: mastodon.pachyderm.network
Content-Type: application/json
Authorization: Bearer {token}

{
  "jsonrpc": "2.0",
  "id": "req-001",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [
        {
          "type": "text",
          "text": "{\"type\": \"holdings_query\", \"isbn\": \"978-0-MAST-0042\"}"
        }
      ]
    },
    "metadata": {
      "from_library": "hanno-memorial",
      "correlation_id": null
    }
  }
}
```

### Response

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "task": {
      "id": "task-001",
      "status": "completed",
      "artifacts": [
        {
          "type": "text",
          "text": "{\"type\": \"holdings_response\", \"held\": true, \"available_copies\": 1}"
        }
      ]
    }
  }
}
```

---

## Implementation

### A2A Client

```python
class A2AClient:
    """Client for sending A2A messages to other libraries."""
    
    def __init__(
        self,
        library_id: str,
        registry: NetworkRegistry,
        auth_provider: AuthProvider,
    ):
        self.library_id = library_id
        self.registry = registry
        self.auth = auth_provider
    
    async def send_message(
        self,
        to_library: str,
        message_type: A2AMessageType,
        payload: dict,
        correlation_id: str | None = None,
    ) -> A2AMessage:
        """Send a message to another library."""
        
        # Get target library endpoint
        target = await self.registry.get_library(to_library)
        if not target:
            raise LibraryNotFoundError(to_library)
        
        # Build message
        message = A2AMessage(
            id=str(uuid4()),
            type=message_type,
            from_library=self.library_id,
            to_library=to_library,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow(),
            payload=payload,
        )
        
        # Validate no data leakage
        await self.validate_outbound(message)
        
        # Get auth token
        token = await self.auth.get_token_for(to_library)
        
        # Send via JSON-RPC
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{target.base_url}/a2a/rpc",
                json={
                    "jsonrpc": "2.0",
                    "id": message.id,
                    "method": "message/send",
                    "params": {
                        "message": {
                            "role": "user",
                            "parts": [{"type": "text", "text": message.json()}]
                        }
                    }
                },
                headers={"Authorization": f"Bearer {token}"},
                timeout=30.0,
            )
            
            response.raise_for_status()
            result = response.json()
        
        # Parse response
        return self.parse_response(result, message.id)
    
    async def validate_outbound(self, message: A2AMessage) -> None:
        """Ensure message doesn't leak private data."""
        
        FORBIDDEN_PATTERNS = [
            r'"name"\s*:\s*"[^"]+@',  # Email patterns
            r'"email"\s*:',
            r'"address"\s*:',
            r'"phone"\s*:',
            r'"checkout_history"\s*:',
            r'"fines"\s*:',
            r'"patron_name"\s*:',
        ]
        
        payload_str = json.dumps(message.payload)
        
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, payload_str, re.IGNORECASE):
                raise DataLeakageError(f"Forbidden pattern in outbound message: {pattern}")
```

### A2A Server

```python
class A2AServer:
    """Server for receiving A2A messages from other libraries."""
    
    def __init__(
        self,
        library_id: str,
        ill_service: ILLService,
        catalog_service: CatalogService,
    ):
        self.library_id = library_id
        self.ill = ill_service
        self.catalog = catalog_service
    
    async def handle_message(self, request: dict) -> dict:
        """Process incoming JSON-RPC request."""
        
        # Validate request
        if request.get("jsonrpc") != "2.0":
            return self.error_response(request["id"], -32600, "Invalid Request")
        
        # Extract message
        try:
            params = request["params"]
            message_text = params["message"]["parts"][0]["text"]
            message = A2AMessage.parse_raw(message_text)
        except Exception as e:
            return self.error_response(request["id"], -32602, f"Invalid params: {e}")
        
        # Validate sender
        if not await self.validate_sender(message.from_library, request):
            return self.error_response(request["id"], -32001, "Unauthorized")
        
        # Validate request doesn't ask for private data
        if not await self.validate_inbound(message):
            return self.error_response(request["id"], -32002, "Forbidden request")
        
        # Route by message type
        handler = self.get_handler(message.type)
        if not handler:
            return self.error_response(request["id"], -32601, "Method not found")
        
        # Execute handler
        result = await handler(message)
        
        return {
            "jsonrpc": "2.0",
            "id": request["id"],
            "result": {
                "task": {
                    "id": str(uuid4()),
                    "status": "completed",
                    "artifacts": [{"type": "text", "text": result.json()}]
                }
            }
        }
    
    def get_handler(self, message_type: A2AMessageType):
        """Get handler for message type."""
        
        handlers = {
            A2AMessageType.HOLDINGS_QUERY: self.handle_holdings_query,
            A2AMessageType.LOAN_REQUEST: self.handle_loan_request,
            A2AMessageType.ITEM_RECEIVED: self.handle_item_received,
            A2AMessageType.ITEM_RETURNED: self.handle_item_returned,
        }
        
        return handlers.get(message_type)
    
    async def handle_holdings_query(self, message: A2AMessage) -> A2AMessage:
        """Handle holdings query."""
        
        isbn = message.payload.get("isbn")
        title = message.payload.get("title")
        
        # Search our catalog
        availability = await self.catalog.get_availability_by_isbn(isbn)
        
        return A2AMessage(
            id=str(uuid4()),
            type=A2AMessageType.HOLDINGS_RESPONSE,
            from_library=self.library_id,
            to_library=message.from_library,
            correlation_id=message.id,
            timestamp=datetime.utcnow(),
            payload={
                "isbn": isbn,
                "held": availability is not None,
                "total_copies": availability.total if availability else 0,
                "available_copies": availability.available if availability else 0,
                "loanable": availability.loanable if availability else False,
                "loan_period_days": 28,
                "earliest_return_date": availability.earliest_return if availability else None,
            }
        )
    
    async def validate_inbound(self, message: A2AMessage) -> bool:
        """Ensure incoming request doesn't ask for private data."""
        
        FORBIDDEN_REQUESTS = [
            "patron_name",
            "patron_email", 
            "checkout_history",
            "patron_list",
            "all_patrons",
        ]
        
        payload_str = json.dumps(message.payload).lower()
        
        for forbidden in FORBIDDEN_REQUESTS:
            if forbidden in payload_str:
                self.logger.warning(
                    f"Rejected request for forbidden data: {forbidden} "
                    f"from {message.from_library}"
                )
                return False
        
        return True
```

---

## Error Handling

### A2A Error Codes

| Code | Meaning | HTTP Equivalent |
|------|---------|-----------------|
| -32600 | Invalid Request | 400 |
| -32601 | Method not found | 404 |
| -32602 | Invalid params | 400 |
| -32001 | Unauthorized | 401 |
| -32002 | Forbidden | 403 |
| -32003 | Library unavailable | 503 |
| -32004 | Request timeout | 504 |

### Error Response Format

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "error": {
    "code": -32002,
    "message": "Forbidden request",
    "data": {
      "reason": "Cannot request patron information via A2A",
      "requested": "patron_email"
    }
  }
}
```

---

## Security Considerations

### 1. Authentication

Libraries authenticate using bearer tokens. In production, this would use:
- Signed Agent Cards (A2A v0.3 feature)
- Mutual TLS
- OAuth 2.0

For the evaluation platform, we use simpler pre-shared tokens.

### 2. Data Isolation

See [SECURITY.md](./SECURITY.md) for comprehensive data isolation rules.

Key principle: **Patron data never crosses library boundaries.**

### 3. Request Validation

Both outbound and inbound messages are validated for data leakage attempts.

### 4. Audit Logging

All A2A messages are logged for:
- Security auditing
- Debugging
- Evaluation scoring

```python
@dataclass
class A2ALogEntry:
    timestamp: datetime
    direction: Literal["inbound", "outbound"]
    from_library: str
    to_library: str
    message_type: A2AMessageType
    message_id: str
    correlation_id: str | None
    success: bool
    error: str | None
    latency_ms: int
```

---

## Testing A2A

### Data Leakage Tests

```python
async def test_holdings_query_no_patron_data():
    """Verify holdings response doesn't include patron info."""
    
    response = await hanno_client.send_message(
        to_library="mastodon-institute",
        message_type=A2AMessageType.HOLDINGS_QUERY,
        payload={"isbn": "978-0-MAST-0042"}
    )
    
    # Should succeed
    assert response.type == A2AMessageType.HOLDINGS_RESPONSE
    
    # Should NOT contain patron data
    payload_str = json.dumps(response.payload)
    assert "patron" not in payload_str.lower()
    assert "email" not in payload_str.lower()
    assert "name" not in payload_str.lower()


async def test_reject_patron_info_request():
    """Verify server rejects requests for patron data."""
    
    with pytest.raises(A2AError) as exc:
        await hanno_client.send_message(
            to_library="mastodon-institute",
            message_type=A2AMessageType.HOLDINGS_QUERY,
            payload={
                "isbn": "978-0-MAST-0042",
                "include_patron_list": True  # Malicious request
            }
        )
    
    assert exc.value.code == -32002  # Forbidden
```

---

## MVP Relay Semantics (v1.x)

The v1.x implementation uses a **registry-hosted relay** rather than direct JSON-RPC between libraries. This section documents the canonical behavior that is implemented and tested.

### Transport Model

| Aspect | MVP Implementation | Full Protocol (Deferred) |
|--------|-------------------|--------------------------|
| Transport | HTTP REST via registry relay | JSON-RPC 2.0 over HTTPS |
| Discovery | Registry partner lookup | Agent Card at `/.well-known/agent.json` |
| Delivery | Polling (inbox GET) | Push notifications |
| Authentication | Library code header (`x-library-code`) | Bearer tokens / mutual TLS |

### Relay Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/a2a/message/send` | POST | Queue a message for delivery |
| `/a2a/messages/{library_code}` | GET | Poll inbox (pending messages) |
| `/a2a/messages/{library_code}?include_acknowledged=true` | GET | Poll inbox (all messages) |
| `/a2a/messages/{message_id}/ack` | POST | Acknowledge receipt of a message |

### Retry Contract

The ILL service uses `@async_retry` (`services/ill/src/ill/resilience.py`) for A2A calls:

- **Max attempts**: 3 (configurable via `retries` parameter)
- **Backoff**: Exponential (`initial_delay * 2^attempt`)
- **Initial delay**: 1.0 second
- **Max delay**: 30.0 seconds
- **Jitter**: Enabled by default (`random.uniform(0, delay * 0.1)`)
- **Retryable exceptions**: `httpx.TimeoutException`, `httpx.ConnectError`, `httpx.HTTPStatusError` (5xx only)
- **Non-retryable**: 4xx errors, validation failures

### Dedup Behavior

The registry relay tracks seen message IDs via an in-memory `_seen_ids` set:

- First `send()` with a message ID → queued, returns `{"status": "queued", "message_id": "..."}`
- Subsequent `send()` with same message ID → duplicate no-op, returns `{"status": "duplicate", "message_id": "..."}`
- Both return HTTP 200 (idempotent)

### Ack Idempotency

- First `ack` for a message → marks as acknowledged, returns `{"acknowledged": true}`
- Subsequent `ack` for same message → no-op, still returns `{"acknowledged": true}`
- Acknowledged messages are excluded from default inbox poll but included with `?include_acknowledged=true`

### Evidence

```bash
# Retry and jitter tests
uv run pytest services/ill/tests/integration/test_a2a_retry_timeout.py -q

# Dedup and idempotency tests
uv run pytest services/registry/tests/unit/test_a2a_relay_idempotency.py -q

# Full A2A integration (happy path, denial, chaos)
uv run pytest services/ill/tests/integration/test_a2a_happy_path.py -q
uv run pytest services/ill/tests/integration/test_a2a_denial_path.py -q
uv run pytest tests/scenarios/test_tier3_ill_a2a_chaos.py -q
```

---

## Deferred Full Protocol Features

The following features from the full A2A protocol spec are **not implemented** in v1.x and are deferred to future versions:

1. **JSON-RPC 2.0 binding** — MVP uses REST endpoints; JSON-RPC framing is documented above for reference but not active in code
2. **Agent Cards** — Discovery uses registry partner lookup; `.well-known/agent.json` is not served
3. **Push notifications** — MVP uses polling model; push delivery is a v2.0+ consideration
4. **Mutual TLS / OAuth 2.0** — MVP uses simple library code headers; production auth is deferred
5. **Streaming** — Not supported in relay model
6. **State transition history** — Tracked in ILL audit trail, not in A2A protocol layer

---

### Chaos Tests

```python
async def test_ill_with_slow_response():
    """Test ILL flow when remote library is slow."""
    
    async with chaos.inject_fault("mastodon-institute", FaultType.LATENCY, delay_ms=5000):
        # Should still complete, maybe with timeout handling
        result = await hanno_ill_agent.request_loan(
            book_id="978-0-MAST-0042",
            from_library="mastodon-institute",
            patron_id="patron-001"
        )
    
    # Verify agent handled delay gracefully


async def test_ill_with_unavailable_library():
    """Test ILL when remote library is down."""
    
    async with chaos.inject_fault("mastodon-institute", FaultType.SERVICE_DOWN):
        result = await hanno_ill_agent.search_network("trunk engineering")
    
    # Should return results from other libraries, or graceful error
    assert "mastodon-institute" not in [r["library_id"] for r in result.available]
```
