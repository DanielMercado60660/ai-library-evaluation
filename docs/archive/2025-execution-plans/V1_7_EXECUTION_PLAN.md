# v1.7 Execution Plan: Live Federated Services

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.7` (live multi-library service federation with real HTTP resolution)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: v1.4 monkeypatched fixture-based federation
- Related Workstream: infrastructure-services, a2a-network, evaluation-harness

## Objective
Upgrade the v1.4 fixture-based federated topology into live service federation where spoke holdings are resolved through real HTTP calls between running services:
1. Seed spoke library holdings into actual catalog service databases.
2. Replace monkeypatched ILL resolution with real HTTP calls to catalog and registry services.
3. Run full ILL lifecycle tests against live multi-library service instances.
4. Validate end-to-end A2A message flow through the registry relay between live services.

## Context: v1.4 Foundation
v1.4 established the deterministic data plane:
- `data/network_seed_manifest.json` — 635-book corpus partitioned across 5 libraries
- `spoke_holdings` fixture — loads spoke catalogs from JSON batch files
- `federated_ill_client` fixture — monkeypatches `call_catalog`, `call_registry`, `call_circulation`, `call_service`
- `_is_known_local_book()` — extracted for override, bypasses hardcoded local-book check

v1.7 replaces the monkeypatch layer with real service calls while preserving the same test assertions.

## v1.7 Success Criteria
1. Spoke library catalogs are seeded into real (in-process or docker-compose) catalog databases.
2. ILL routes resolve spoke holdings via live HTTP calls — no monkeypatching in v1.7 integration tests.
3. A2A messages flow through the live registry relay for cross-library ILL requests.
4. The `seed_network.py` orchestrator writes spoke holdings into service databases (not just static files).
5. Full ILL lifecycle (local-miss -> ILL request -> A2A notification -> spoke fulfillment) runs end-to-end.
6. `uv run pytest -q` remains green (v1.4 fixture-based tests continue to pass alongside live tests).

## In Scope
1. Multi-tenant or multi-instance catalog service strategy for spoke libraries.
2. Seed orchestrator upgrade (`seed_network.py`) to provision spoke catalogs into service databases.
3. Live federation integration tests (separate from v1.4 fixture-based tests).
4. Docker-compose configuration for multi-library topology (if multi-instance approach chosen).
5. ILL route enhancements to resolve spoke holdings via catalog service lookups.
6. Documentation and runbook updates for live federation workflow.

## Out of Scope
1. Production multi-tenant isolation or access control.
2. Horizontal scaling or load balancing across library instances.
3. Operator UI integration for federation management (`v2.0`).
4. Cross-model comparison (`v2.1`).

## Dependencies
1. `v1.4` federated data topology (manifest, partitioning, batch files) is stable.
2. `v1.5` run control plane provides run-scoped artifact output (optional but recommended).
3. `v1.6` operator shell and local preflight path support multi-service startup.

## Architecture Decision: Option B (Multi-Instance) — Implemented

**Option B (Multi-Instance Catalog) was selected** as the correct path toward production alpha (v2.0):
- One catalog service instance per library (5 total), each on a different port (8001, 8011-8014).
- Each instance has its own SQLite database with isolated book data.
- Registry maps library codes to service endpoints via `catalog_url` field.
- ILL routes resolve spoke holdings by calling the correct catalog instance via registry lookup.
- Docker-compose deploys all 5 catalog instances as separate containers.

**Why Option B over Option A (Multi-Tenant):**
- **Realistic isolation**: Each library has its own service + database, mirroring real-world federation.
- **No schema changes**: Catalog BookModel/BookInstanceModel stay untouched — isolation is at the service/DB level.
- **Clean routing**: Registry's `catalog_url` field becomes the service discovery mechanism.
- **Docker-ready**: Each spoke is a separate container with its own config.

## Planned Implementation Footprint

### Phase A: Catalog Multi-Tenancy (`v1.7-a`)

1. Catalog service changes
- Update:
  - `services/catalog/src/catalog/models.py` — add `library_code` field to BookModel (default: `"hanno-memorial"`)
  - `services/catalog/src/catalog/routes.py` — add `library_code` query parameter to search/list endpoints
  - `services/catalog/src/catalog/seed.py` or equivalent — support seeding with library ownership

2. Seed orchestrator upgrade
- Update:
  - `scripts/seed_network.py` — write spoke holdings into catalog DB with `library_code` tags
  - `scripts/seed_db.py` — tag existing Hanno books with `library_code: "hanno-memorial"`

3. Tests
- New:
  - `services/catalog/tests/unit/test_multi_tenant_books.py` — library_code filtering
- Update:
  - `services/catalog/tests/unit/test_search_filters.py` — verify default library_code behavior

Milestone (`v1.7-a`)
1. Owner placeholder: TBD
2. Deliverable: catalog service supports multi-tenant book ownership.
3. Acceptance checks:
   - books can be queried by library_code
   - existing single-library tests pass without modification
4. Evidence command(s):
   - `uv run pytest services/catalog/tests -q`

### Phase B: ILL Live Resolution (`v1.7-b`)

1. ILL route enhancements
- Update:
  - `services/ill/src/ill/routes.py` — replace `_is_known_local_book()` with catalog service query; resolve spoke books via `call_catalog` with `library_code` filter
  - `services/ill/src/ill/routes.py` — `/inbound/query` resolves spoke ISBNs via live catalog lookup

2. Registry integration
- Update:
  - `services/registry/src/registry/routes.py` — ensure partner library records include catalog endpoint metadata (if needed for multi-instance future)

3. Tests
- New:
  - `tests/scenarios/test_live_federation.py` — integration tests using real in-process services (no monkeypatching)
- Existing:
  - v1.4 fixture-based tests (`test_ill_network_holdings_resolution.py`) continue to pass unchanged

Milestone (`v1.7-b`)
1. Owner placeholder: TBD
2. Deliverable: ILL routes resolve spoke holdings via live catalog calls.
3. Acceptance checks:
   - ILL request for spoke book succeeds via real HTTP call chain
   - holdings query for spoke ISBN returns held=True from live catalog
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_live_federation.py -q`
   - `uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q`

### Phase C: End-to-End Federation Lifecycle (`v1.7-c`)

1. Full lifecycle tests
- New:
  - `tests/scenarios/test_live_federation.py` — expanded with:
    - local-miss -> spoke-hit -> ILL request -> A2A notification -> spoke fulfillment
    - cross-spoke resolution (patron at Hanno requests book from Mastodon via live services)
    - holdings query round-trip through live catalog and registry

2. Docker-compose update (optional)
- Update:
  - `docker-compose.yml` — add federated seed step or health check for multi-tenant mode

3. Documentation
- Update:
  - `docs/development/BENCHMARK_RUNBOOK.md` — v1.7 live federation commands
  - `docs/status/PROJECT_STATUS.md` — v1.7 section
  - `docs/status/BENCHMARK_V1_DEFINITION_OF_DONE.md` — v1.7 completion matrix
  - `docs/status/ARCHITECTURE_DRIFT_REPORT.md` — close v1.7 targets

Milestone (`v1.7-c`)
1. Owner placeholder: TBD
2. Deliverable: full end-to-end federated ILL lifecycle with live services.
3. Acceptance checks:
   - complete ILL lifecycle runs without monkeypatching
   - A2A messages flow through live registry relay
   - all v1.4 fixture-based tests continue to pass
4. Evidence command(s):
   - `uv run pytest -q`
   - `uv run python scripts/seed_network.py --mode federated`
   - `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

## Test Plan and Acceptance Matrix
1. Unit
- catalog multi-tenant filtering
- library_code default behavior backward compatibility

2. Integration
- live ILL spoke resolution (no monkeypatching)
- live A2A message flow for federated requests
- live holdings query resolution

3. Regression
- v1.4 fixture-based tests pass unchanged
- all existing service tests pass without modification

4. Full gates
- `uv run pytest -q`
- `uv run pytest tests/scenarios -q`
- `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

## Risks and Mitigations
1. Risk: `library_code` column breaks existing catalog queries.
- Mitigation: default to `"hanno-memorial"`; existing queries return same results without filter.

2. Risk: live federation tests are slower and flakier than fixture-based tests.
- Mitigation: keep v1.4 fixture tests as fast deterministic baseline; live tests run as separate suite.

3. Risk: multi-tenant approach is insufficient for realistic federation evaluation.
- Mitigation: design for multi-instance upgrade path; multi-tenant is stepping stone, not endpoint.

4. Risk: seed orchestrator DB writes conflict with existing single-library seed path.
- Mitigation: `--federated` flag keeps the two paths separate; single-library seed unchanged.

## Definition of Done
`v1.7` is complete when:
1. Spoke library holdings are seeded into catalog service database with ownership tags.
2. ILL routes resolve spoke books via live catalog HTTP calls (no monkeypatching).
3. Full ILL lifecycle runs end-to-end through live services with A2A message verification.
4. v1.4 fixture-based tests continue to pass alongside live federation tests.
5. Documentation and runbook reflect live federation workflow.
6. Global regression suite remains green.

## Implementation Summary

### Files Created (5)
| File | Purpose |
|------|---------|
| `scripts/seed_spoke_catalog.py` | CLI seeder for individual library catalog databases from network manifest |
| `scripts/seed_registry_federation.py` | Seeds registry with spoke catalog_url entries |
| `scripts/seed_docker_federation.sh` | Docker-compose federation provisioning script |
| `tests/scenarios/test_spoke_catalog_seeding.py` | Spoke seeding correctness tests (11 tests) |
| `tests/scenarios/test_live_federation.py` | Live HTTP federation integration tests (11 tests) |

### Files Modified (9+)
| File | Change |
|------|--------|
| `services/catalog/src/catalog/routes.py` | LIBRARY_CODE/LIBRARY_NAME env vars, `/library/info` endpoint |
| `services/catalog/src/catalog/schemas.py` | LibraryInfoResponse model, library_code in HealthResponse |
| `services/catalog/src/catalog/main.py` | Dynamic title from env var |
| `shared/src/shared/http_client.py` | `call_url()` and `call_remote_catalog()` |
| `services/registry/src/registry/schemas.py` | `catalog_url` on PartnerLibrary CRUD schemas |
| `services/registry/src/registry/routes.py` | catalog_url wired through all CRUD paths |
| `services/ill/src/ill/routes.py` | Step 3b spoke verification via call_remote_catalog |
| `services/ill/src/ill/schemas.py` | Optional `isbn` field on ILLRequestCreate |
| `scripts/seed_network.py` | `--mode provision` for DB provisioning |
| `data/network_seed_manifest.json` | `endpoints` section with port/docker_host per library |
| `docker-compose.yml` | 4 spoke catalog services + volumes |
| `tests/scenarios/conftest.py` | `live_spoke_catalogs` and `live_federation_client` fixtures |

### Port Layout
| Port | Service |
|------|---------|
| 8000 | agents |
| 8001 | catalog (hanno-memorial) — unchanged |
| 8002 | circulation |
| 8003 | ill |
| 8004 | registry |
| 8011 | catalog-mastodon |
| 8012 | catalog-mammoth |
| 8013 | catalog-ivory |
| 8014 | catalog-tusk |

### Test Baseline
- `uv run pytest -q` → 547 passed, 6 skipped, 10 xfailed (+30 from v1.6)
- `uv run pytest agents/tests -q` → 145 passed

## Follow-On Handoff
After `v1.7` completion:
1. `docs/status/V1_7_5_EXECUTION_PLAN.md` — formalize architecture-decision governance, API/schema compatibility checks, and dependency-boundary enforcement before `v2.0`.
2. `docs/status/V1_8_EXECUTION_PLAN.md` — security and operability foundations.
3. Multi-instance federation is now the baseline for all subsequent versions.
