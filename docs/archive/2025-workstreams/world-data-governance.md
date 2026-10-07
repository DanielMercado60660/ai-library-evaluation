# Workstream: World and Data Governance

## Doc Header
- Doc Status: In Progress
- Owner: AI Librarian Team
- Last Verified: 2026-02-10
- Scope: Fictional-world integrity, synthetic data quality, and governance enforcement
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: scattered world/data status notes
- Related Workstream: world-data-governance

## Objective
Preserve fictional-world integrity and ensure all evaluation datasets/scenarios remain synthetic and policy-compliant.

## Current Reality
1. Synthetic dataset packs and patron/catalog seeds are implemented and actively used in tests.
2. Scenario suites enforce fictional-world constraints and benchmark reproducibility.
3. Frontend/content polish is ongoing to eliminate remaining real-world leakage risks.

## Implemented Footprint
1. Data and seed manifests:
   - `data/network_seed_manifest.json`
   - `data/hanno_patrons.json`
   - `data/batch_*.json`
2. Seed/validation scripts:
   - `scripts/seed_manifest_validator.py`
   - `scripts/seed_network.py`
   - `scripts/validate_catalog.py`
3. Guardrail coverage:
   - `tests/scenarios/test_synthetic_guardrails.py`
   - `tests/scenarios/test_federated_seed_manifest.py`

## Remaining Gaps
1. Stronger automated checks for frontend sample/featured content integrity.
2. Formal governance checklist linking content updates to benchmark validation runs.
3. Dataset change-log discipline for evaluator-facing comparison reproducibility.

## Next 3 Milestones
1. Owner placeholder: TBD
   - Deliverable: UI content integrity checker for fictional-only references.
   - Acceptance checks: CI fails on known real-world author/title leakage patterns.
   - Evidence command(s): `rg -n "Orwell|Austen|Shakespeare" frontend/src docs`
2. Owner placeholder: TBD
   - Deliverable: governance checklist linking data updates to required validation commands.
   - Acceptance checks: checklist referenced by data and evaluation docs.
   - Evidence command(s): `rg -n "seed|validate|fictional|governance" docs scripts`
3. Owner placeholder: TBD
   - Deliverable: dataset release-note template including comparability impact.
   - Acceptance checks: next dataset increment documents compatibility impact for benchmark scoring.
   - Evidence command(s): `rg -n "manifest|schema|compatibility" docs/status tests/scenarios`

## Definition of Done
All active datasets, scenarios, and UI-facing exemplars are synthetic-world compliant with traceable validation evidence.

## Dependencies
- evaluation-harness
- infrastructure-services

## Risks
- Real-world leakage undermining benchmark validity.
- Inconsistent dataset revisions reducing cross-run comparability.
