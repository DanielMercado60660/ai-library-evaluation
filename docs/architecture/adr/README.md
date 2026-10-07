# Architecture Decision Records (ADRs)

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Governance process for architecture-significant decisions
- Source of Truth: `docs/status/PROJECT_STATUS.md`

## What is an ADR?

An Architecture Decision Record captures a significant decision that affects the structure, behavior, or quality attributes of the system. ADRs make decisions explicit, traceable, and reviewable.

## When to Write an ADR

Write an ADR when a decision:
- Changes the module structure or service topology
- Introduces or replaces a framework, protocol, or major library
- Alters the data model, API contract, or artifact schema
- Affects cross-service communication patterns
- Changes the evaluation or benchmark methodology

Do NOT write an ADR for routine implementation choices (variable naming, test structure, minor refactors).

## How to Create an ADR

1. Copy `ADR_TEMPLATE.md` to `ADR-NNN-short-kebab-title.md`
2. Use the next available number from `INDEX.md`
3. Fill in all four required sections: Status, Context, Decision, Consequences
4. Add the entry to `INDEX.md`
5. Run `uv run python scripts/check_adr_links.py --strict` to validate

## Naming Convention

`ADR-NNN-short-kebab-title.md` where NNN is a zero-padded three-digit number.

## Status Lifecycle

- **Proposed**: Under discussion, not yet accepted
- **Accepted**: Decision is in effect and implemented
- **Superseded by ADR-NNN**: Replaced by a newer decision
- **Deprecated**: No longer relevant but kept for historical reference

## Validation

The ADR checker runs in CI and verifies:
- Every ADR file on disk is listed in INDEX.md
- Every INDEX.md entry has a corresponding file
- Each ADR has all four required sections

```bash
uv run python scripts/check_adr_links.py --strict
```
