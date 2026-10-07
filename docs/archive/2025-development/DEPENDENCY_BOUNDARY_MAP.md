# Dependency Boundary Map

## Doc Header
- Doc Status: Implemented
- Owner: AI Librarian Team
- Last Verified: 2026-02-09
- Scope: Allowed and forbidden import paths between project layers
- Source of Truth: `docs/status/PROJECT_STATUS.md`
- Related Workstream: infrastructure-services

## Purpose

Define the import dependency DAG so layering stays coherent as the codebase scales. Violations are caught by `scripts/check_dependency_boundaries.py` and enforced in CI.

## Import DAG

```
external packages <── shared <── services/{x}
                        ^
                        └─────── agents

scripts, tests: exempted (may import from any layer)
```

- `shared` depends only on external packages (pydantic, httpx)
- Each service depends on `shared` and its own package
- `agents` depends on `shared` and its own package
- Services do NOT import from each other or from agents
- Agents do NOT import from service packages (they use HTTP/MCP)
- Scripts and tests may import from any layer

## Boundary Rules

| Source Layer | Allowed Imports | Forbidden Imports |
|---|---|---|
| `shared/src/shared/` | External packages only | `agents`, `catalog`, `circulation`, `ill`, `registry` |
| `services/catalog/src/` | `shared`, `catalog` (own), external | `agents`, `circulation`, `ill`, `registry` |
| `services/circulation/src/` | `shared`, `circulation` (own), external | `agents`, `catalog`, `ill`, `registry` |
| `services/ill/src/` | `shared`, `ill` (own), external | `agents`, `catalog`, `circulation`, `registry` |
| `services/registry/src/` | `shared`, `registry` (own), external | `agents`, `catalog`, `circulation`, `ill` |
| `agents/src/` | `shared`, `agents` (own), external | `catalog`, `circulation`, `ill`, `registry` |
| `scripts/` | Any (exempted) | -- |
| `tests/` | Any (exempted) | -- |

## How It Works

The boundary checker (`scripts/check_dependency_boundaries.py`) uses Python's `ast` module to parse import statements from source files. It:
1. Scans only `src/` directories (not scripts or tests)
2. Extracts the top-level module name from each import
3. Checks against the forbidden set for that source directory
4. Reports violations with file path and line number

Only absolute imports are checked. Relative imports within a package (e.g., `from .db import get_session`) are always allowed.

## Adding a New Service

When adding a new service package:
1. Add its source directory and forbidden set to `BOUNDARY_RULES` in `scripts/check_dependency_boundaries.py`
2. Add it to the forbidden set of all other layers (services, agents, shared)
3. Update this document's boundary rules table
4. Run `uv run python scripts/check_dependency_boundaries.py --strict` to verify

## Validation

```bash
uv run python scripts/check_dependency_boundaries.py --strict
uv run pytest tests/scenarios/test_dependency_boundaries.py -q
```
