# Contract Compatibility Policy

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Rules for evolving benchmark artifact schemas and service API payloads without breaking consumers
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Related Workstream: evaluation-harness, infrastructure-services

## Purpose

Protect consumers of benchmark artifacts and run APIs from unannounced breaking changes. Ensure schema evolution is intentional, versioned, and test-backed.

## Additive (Non-Breaking) Changes

New optional fields in JSON artifacts are always allowed. Consumers must ignore unknown keys. Examples:
- Adding `new_metric` to the report summary
- Adding optional metadata to manifest scenario entries
- Adding new enum values to taxonomy categories

Additive changes do NOT require a schema version bump.

## Breaking Changes

The following are breaking changes and require the full governance process:
- Removing a required field
- Renaming a required field
- Changing a field's type (e.g., string to integer)
- Changing enum value semantics (e.g., redefining what "passed" means)
- Restructuring nested objects

**Breaking change process:**
1. Write an ADR documenting the change and rationale (see `docs/architecture/adr/README.md`)
2. Bump the `schema_version` field in the affected artifact
3. Create or update the golden fixture under `tests/fixtures/golden/`
4. Update compatibility tests in `tests/scenarios/test_contract_compatibility.py`
5. Provide a deprecation window of at least one minor version

## Current Schema Versions

| Artifact | Schema Version | Golden Fixture |
|----------|---------------|----------------|
| Benchmark report | 1.1 (baseline) | `tests/fixtures/golden/benchmark-report-v1.1.json` |
| Run index | 1.5 | `tests/fixtures/golden/run-index-v1.5.json` |
| Scenario manifest | 1.4 | `tests/fixtures/golden/scenario-manifest-v1.4.json` |

Note: The benchmark report uses `schema_version: "1.5"` when generated with `--run-id` and `"1.3"` without. The v1.1 golden fixture defines the minimum required field set that all versions must maintain.

## Golden Fixture Requirement

Each schema version must have a minimal valid fixture under `tests/fixtures/golden/`. Golden fixtures define the contract: they contain all required fields with representative values. Compatibility tests validate that current code can consume golden fixtures without error.

## Deprecation Window

Deprecated fields must remain for at least one minor version cycle after the deprecation ADR is accepted. Deprecated fields should be documented in the ADR with:
- The version in which they were deprecated
- The version in which they will be removed
- The replacement (if any)

## Validation

```bash
uv run pytest tests/scenarios/test_contract_compatibility.py -q
```
