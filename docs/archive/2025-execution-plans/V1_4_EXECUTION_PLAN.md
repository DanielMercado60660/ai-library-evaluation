# v1.4 Execution Plan: Federated Data Topology

## Doc Header
- Doc Status: Planned
- Owner: TBD
- Last Verified: 2026-02-09
- Scope: Delivery plan for `v1.4` (hub/spoke catalog seeding + deterministic federated ILL dataset topology)
- Source of Truth: `docs/status/VERSION_LADDER_PROPOSAL.md`
- Supersedes: Ad-hoc notes about batch seeding and partner-library data setup
- Related Workstream: infrastructure-services, a2a-network, evaluation-harness, world-data-governance

## Objective
Create a deterministic network data plane between `v1.3` and `v2.0` so ILL evaluation reflects hub-and-spoke reality:
1. Promote local single-library seed flows into manifest-driven multi-library seeding.
2. Map existing catalog batch files into explicit library ownership partitions.
3. Align registry partner records with seeded holdings so ILL requests can resolve to real spoke inventories.
4. Preserve deterministic run/replay behavior for benchmark scenarios and CI.

## v1.4 Success Criteria
1. A single command path seeds hub and spoke datasets reproducibly from versioned manifest inputs.
2. All prepared catalog batches are accounted for in a documented partition map (no orphan batch files).
3. Registry partner libraries and seeded holdings references are consistent.
4. ILL scenario coverage proves local-miss/network-hit behavior against seeded spoke data.
5. `uv run pytest -q` remains green after integration.

## In Scope
1. Versioned network seed manifest and validation tooling.
2. Hub/spoke catalog partition seeding from existing `data/batch_*.json` sources.
3. Registry seeding alignment with partner holdings metadata.
4. ILL scenario fixture updates for deterministic network lookup paths.
5. Seed-report artifacts for deterministic count/evidence checks.
6. Runbook/status documentation updates for repeatable network seeding operations.

## Out of Scope
1. Dynamic production ingest pipelines and real-time ETL.
2. Cloud-hosted multi-tenant catalog federation.
3. Public operator UI for topology editing (`v2.0+` UX concern).
4. Cross-model performance comparison (`v2.1`).

## Dependencies
1. `v1.3` resilience contracts remain intact for A2A and retry semantics.
2. Existing seed datasets remain the canonical source files under `data/`.
3. Registry service remains the canonical partner-library identity source.
4. Deterministic scenario and artifact conventions from `v1.1`-`v1.3` remain mandatory.

## Public Interface and Contract Changes
1. Network seed manifest contract
- File: `data/network_seed_manifest.json`
- Required fields:
  - `schema_version`
  - `hub`
  - `spokes[]`
  - `batch_assignments[]`
  - `library_catalog_ids[]`
  - `seed_mode` (`single_library` | `federated`)

2. New network seed runner contract
- File: `scripts/seed_network.py`
- Responsibilities:
  - validate manifest before write operations
  - seed catalog partitions per library role
  - seed registry records and partner metrics alignment
  - emit deterministic seed summary artifact

3. New seed evidence artifact
- File: `artifacts/network-seed-report.json`
- Required fields:
  - `report_version`
  - `run_id`
  - `seed_mode`
  - `library_summaries[]`
  - `batch_coverage`
  - `warnings[]`
  - `errors[]`

4. Scenario manifest extension (optional per scenario)
- File: `tests/scenarios/scenario_manifest.json`
- New optional fields:
  - `requires_federated_seed` (boolean)
  - `expected_source_library` (string)
  - `network_lookup_required` (boolean)

## Planned Implementation Footprint
1. Seed orchestration and validators
- New:
  - `scripts/seed_network.py`
  - `scripts/seed_manifest_validator.py`
  - `scripts/seed_partition_catalog.py`
- Update:
  - `scripts/seed_all.py`
  - `scripts/seed_db.py`
  - `scripts/seed_registry.py`

2. Data contract files
- New:
  - `data/network_seed_manifest.json`
- Update:
  - `data/validation_report.json` (batch coverage metadata)

3. Scenario and integration tests
- New:
  - `tests/scenarios/test_federated_seed_manifest.py`
  - `tests/scenarios/test_federated_catalog_partitioning.py`
  - `tests/scenarios/test_ill_network_holdings_resolution.py`
- Update:
  - `tests/scenarios/scenario_manifest.json`
  - `services/ill/tests/integration/` (network lookup expectations)

4. Documentation updates
- Update:
  - `docs/development/BENCHMARK_RUNBOOK.md`
  - `docs/development/QUICK_START.md`
  - `docs/status/PROJECT_STATUS.md`
  - `docs/status/VERSION_LADDER_PROPOSAL.md`
  - `docs/status/ARCHITECTURE_DRIFT_REPORT.md`

## Execution Sequence

### Phase A: Manifest and Topology Contract (`v1.4-a`)
1. Define the canonical federated seed manifest schema.
2. Assign every existing catalog batch to hub or spoke ownership.
3. Add deterministic manifest validation checks:
   - duplicate ID detection
   - missing batch assignment detection
   - library code consistency with registry expectations
4. Add tests that fail on orphan or overlapping assignments.

Milestone (`v1.4-a`)
1. Owner placeholder: TBD
2. Deliverable: schema-validated network seed manifest with complete batch coverage.
3. Acceptance checks:
   - all declared batches resolve to one and only one library partition
   - validation fails on duplicate catalog ID ownership
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_federated_seed_manifest.py -q`
   - `uv run python scripts/seed_manifest_validator.py --check-only`

### Phase B: Multi-Library Seeding Runtime (`v1.4-b`)
1. Implement partition-aware seed orchestration across catalog, registry, and ILL test data.
2. Add deterministic output summaries per library (book counts, instance counts, ID ranges).
3. Add idempotent behavior for re-runs in clean and existing DB states.
4. Emit `artifacts/network-seed-report.json`.

Milestone (`v1.4-b`)
1. Owner placeholder: TBD
2. Deliverable: reproducible network seed runner with artifact evidence.
3. Acceptance checks:
   - repeated runs produce equivalent library counts under same manifest
   - seed report includes full batch coverage and no unresolved assignments
4. Evidence command(s):
   - `uv run python scripts/seed_network.py --mode federated`
   - `uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q`

### Phase C: ILL Federation Readiness (`v1.4-c`)
1. Ensure registry library records map to spoke catalogs represented in the seed manifest.
2. Update ILL test fixtures to require local-miss and spoke-hit lookup behavior.
3. Add deterministic scenario coverage for source library selection under seeded topology.
4. Validate no regression to existing A2A/ILL contract tests.

Milestone (`v1.4-c`)
1. Owner placeholder: TBD
2. Deliverable: ILL network lookup behavior validated against seeded federated topology.
3. Acceptance checks:
   - scenarios can resolve at least one remote source library for non-local holdings
   - source-library references remain valid registry codes
4. Evidence command(s):
   - `uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q`
   - `uv run pytest services/ill/tests/integration/test_a2a_happy_path.py -q`

### Phase D: Reproducibility and Documentation Closeout (`v1.4-d`)
1. Add one-command federated seed path to runbook and quick-start docs.
2. Update status docs with `v1.4` closure evidence and known limitations.
3. Ensure benchmark smoke suites can run against federated seeded topology.
4. Preserve backward compatibility for single-library seed mode where explicitly needed.

Milestone (`v1.4-d`)
1. Owner placeholder: TBD
2. Deliverable: reproducible operator/developer path for federated seed setup.
3. Acceptance checks:
   - docs provide a deterministic setup and verification path
   - smoke suites pass with federated seed mode enabled
4. Evidence command(s):
   - `uv run pytest -q`
   - `uv run python scripts/benchmark_run.py --suite smoke --include-adk`

## Parallelization Plan
1. Parallel lane A (manifest/data contracts)
- seed manifest schema and validator
- batch ownership mapping
- duplicate/orphan protection tests

2. Parallel lane B (seeding runtime)
- partition-aware catalog seeding
- registry alignment hooks
- seed-report artifact generation

3. Parallel lane C (scenario coverage)
- federated ILL scenario updates
- source-library expectation assertions
- smoke-suite compatibility checks

4. Parallel lane D (docs/status)
- runbook and quick-start updates
- project status and ladder updates
- drift report closure linkage

5. Merge point
- run federated seeding end-to-end
- validate benchmark smoke path and regression suite stability

## Test Plan and Acceptance Matrix
1. Unit
- manifest schema validation tests
- duplicate ID ownership rejection tests
- batch coverage completeness tests

2. Integration
- federated seed runner smoke and idempotency tests
- registry/ILL source-library alignment tests
- seed-report schema validation tests

3. Scenario-level
- `uv run pytest tests/scenarios/test_federated_seed_manifest.py -q`
- `uv run pytest tests/scenarios/test_federated_catalog_partitioning.py -q`
- `uv run pytest tests/scenarios/test_ill_network_holdings_resolution.py -q`

4. Full gates
- `uv run pytest -q`
- `uv run python scripts/seed_network.py --mode federated`
- `uv run python scripts/benchmark_run.py --suite scenarios --include-adk`

## Explicit Federated Topology Assertions for v1.4
1. Network Seed Determinism
- Assertion ID: `network_seed_determinism_v1_4`
- Pass condition: same manifest yields same per-library counts and ID ranges.
- Fail condition: repeated seed runs drift in counts or ownership.

2. Catalog Partition Integrity
- Assertion ID: `catalog_partition_integrity_v1_4`
- Pass condition: each catalog ID belongs to exactly one library partition.
- Fail condition: duplicate or unassigned catalog IDs are detected.

3. Registry-Catalog Alignment
- Assertion ID: `registry_catalog_alignment_v1_4`
- Pass condition: every spoke referenced by seeded holdings exists as active registry partner.
- Fail condition: seeded holdings reference unknown or inactive partner code.

4. ILL Remote Holdings Resolution
- Assertion ID: `ill_remote_holdings_resolution_v1_4`
- Pass condition: local-miss scenarios resolve to at least one seeded spoke source.
- Fail condition: ILL lookup returns no eligible spoke despite seeded availability.

## Risks and Mitigations
1. Risk: legacy single-library assumptions break existing tests.
- Mitigation: keep explicit `single_library` mode and migrate tests incrementally.

2. Risk: catalog ID collisions across batches create ambiguous ownership.
- Mitigation: enforce manifest-level uniqueness checks before seeding writes.

3. Risk: partner code naming drift between registry and ILL test fixtures.
- Mitigation: centralize library codes in manifest and validate against registry seeds.

4. Risk: seeded topology increases run/setup complexity.
- Mitigation: publish one-command setup plus deterministic seed-report evidence.

## Definition of Done
`v1.4` is complete when:
1. Federated seed manifest and runner are implemented and deterministic.
2. Existing catalog batches are fully assigned and validated across hub/spoke partitions.
3. Registry and ILL flows reference valid seeded partner libraries.
4. Federated ILL scenario coverage passes with explicit local-miss/network-hit behavior.
5. Documentation includes reproducible setup and verification commands.
6. Global regression command remains green.

## Follow-On Handoff
After `v1.4` completion, create:
1. `docs/status/V1_5_EXECUTION_PLAN.md`

`v1.5` should focus on run control-plane contracts (run identity, run-indexed artifacts, and async orchestration endpoints) while reusing the federated seed guarantees delivered in `v1.4`.
