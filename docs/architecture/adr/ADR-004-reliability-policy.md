# ADR-004: Reliability Policy for Inter-Service Communication

## Status

Accepted

## Context

The AI Library platform relies on HTTP communication between multiple services (catalog, circulation, ILL, registry) and agent tool calls. As the system grows toward production alpha (v2.0), we need codified reliability defaults so new code inherits correct behavior automatically.

Existing patterns are strong but informal:
- Agent tools use `@with_retry(max_attempts=3)` from `agents/src/agents/utils/resilience.py`
- ILL service uses `@async_retry` with exponential backoff + jitter
- Shared HTTP client has a 10s default timeout
- Circuit breaker is available but not universally applied

Without a policy, new inter-service calls could miss retry/timeout handling entirely.

## Decision

All inter-service HTTP calls follow these defaults:

1. **Timeout**: 10 seconds (inherited from `shared/http_client.py`)
2. **Retry budget**: Maximum 3 attempts for transient failures
3. **Retryable failures**: `ConnectionError`, `TimeoutError`, `httpx.TimeoutException`, `httpx.ConnectError` (5xx responses). Client errors (4xx) are NOT retried.
4. **Circuit breaker**: 5 consecutive failures to open, 30s recovery window
5. **Health endpoints**: Must respond within 2 seconds

Agent tool functions that create `httpx.AsyncClient` directly MUST be decorated with `@with_retry` to ensure retry coverage. This is enforced by `scripts/check_resilience_policy.py`.

## Consequences

**Positive:**
- Consistent reliability behavior across all service boundaries
- AST-based checker catches functions that bypass retry policy
- New contributors inherit correct defaults automatically

**Negative:**
- Slight overhead from retry/circuit-breaker wrappers (acceptable for correctness)
- Must remember to update checker if new service call patterns emerge

## Enforcement

- `scripts/check_resilience_policy.py --strict` runs in CI
- `tests/scenarios/test_reliability_policy.py` validates default behaviors
