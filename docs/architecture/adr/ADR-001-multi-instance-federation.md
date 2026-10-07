# ADR-001: Multi-Instance Federation (Option B)

## Status

Accepted

## Context

V1.4 established a federated data topology with 635 books partitioned across 5 libraries, but federation was implemented entirely through monkeypatched test fixtures. V1.7 needed to upgrade this to live service federation with real HTTP resolution.

Two approaches were considered:

- **Option A (Multi-Tenant)**: Single catalog service with a `library_code` column on BookModel. All 635 books in one DB, filtered by ownership tag. Simpler deployment but less realistic isolation.
- **Option B (Multi-Instance)**: One catalog service instance per library, each on a separate port with its own database. Registry maps library codes to service endpoints via `catalog_url` field.

## Decision

We chose **Option B (Multi-Instance)** as the correct path toward production alpha (v2.0).

Each library gets its own catalog service instance parameterized by `LIBRARY_CODE` and `LIBRARY_NAME` environment variables. Docker Compose provisions 4 spoke catalog containers on ports 8011-8014, each with isolated SQLite databases. The registry's existing `catalog_url` field becomes the service discovery mechanism. ILL routes verify spoke holdings via `call_remote_catalog()` with graceful degradation if a spoke is unreachable.

## Consequences

**Positive:**
- Realistic isolation mirrors real-world federation where each library operates independently.
- No schema changes needed: BookModel/BookInstanceModel stay untouched. Isolation is at the service/DB level.
- Clean service discovery: registry `catalog_url` provides the routing mechanism.
- Docker-ready: each spoke is a separate container with its own config.

**Trade-offs:**
- Docker Compose grows by 4 services (9 total) which is heavier for local development.
- Seed orchestration requires per-instance provisioning (`seed_spoke_catalog.py`, `seed_docker_federation.sh`).
- Port management (8011-8014) requires preflight checks.

**References:** `docs/status/V1_7_EXECUTION_PLAN.md`, `docker-compose.yml`, `services/catalog/src/catalog/routes.py`
