# Test Stabilization Checklist

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-08
- Scope: Full test stabilization execution checklist and evidence
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Supersedes: Ad-hoc stabilization notes
- Related Workstream: infrastructure-services

## 1. Infrastructure (`pyproject.toml` import mode, collection pass)
- [x] Enabled importlib test import mode in `pyproject.toml`.
- [x] Removed test-package `__init__.py` files that caused cross-service `tests.conftest` conflicts.
- [x] Collection passes.
  - Evidence: `uv run pytest --collect-only -q`

## 2. Catalog failures fixed
- [x] Fixed genre filtering behavior in catalog HTTP routes.
- [x] Resolved catalog model/mapper conflicts in mixed-suite execution.
- [x] Hardened catalog MCP availability aggregation to avoid relationship/cartesian pitfalls.
- [x] Catalog suites pass.
  - Evidence: `uv run pytest services/catalog/tests -q`

## 3. Circulation failures fixed
- [x] Stabilized SQLModel mapper behavior in circulation models for repeated test metadata setup.
- [x] Corrected checkout flow fallback/update behavior for local instance state and title joins.
- [x] Circulation suites pass.
  - Evidence: `uv run pytest services/circulation/tests -q`

## 4. ILL failures fixed
- [x] Added missing defaults/nullable fields in ILL models.
- [x] Hardened outbound/inbound route fallbacks and state handling in offline test conditions.
- [x] Protected return flow from broker-side runtime errors in local tests.
- [x] ILL suites pass.
  - Evidence: `uv run pytest services/ill/tests -q`

## 5. Agent failures fixed
- [x] Agent tests validated and passing.
  - Evidence: `uv run pytest agents/tests -q`

## 6. Scenario synthetic guardrails green
- [x] Scenario anchors aligned to synthetic catalog entities.
- [x] Guardrail policy test in place and passing.
- [x] Banned real-book marker scan has no matches in scenario directory.
  - Evidence: `uv run pytest --no-cov tests/scenarios/test_synthetic_guardrails.py -q`
  - Evidence: `rg -n "1984|George Orwell|Jane Austen|Dune|The Martian|Project Hail Mary" tests/scenarios`

## 7. Full regression green
- [x] Full repository suite passes.
  - Evidence: `uv run pytest -q`
  - Latest verified result: `364 passed, 15 skipped, 10 xfailed`

## 8. Docs/runbook updated
- [x] Quick start runbook updated with canonical validation flow and explicit optional coverage command.
- [x] Project status dashboard updated with stabilized test state and references.
- [x] This checklist published as the single execution tracker for this cycle.
