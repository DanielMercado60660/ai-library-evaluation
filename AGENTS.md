# Agent guide

Pachyderm Library evaluates stateful AI agents in a fictional library network.
Preserve the distinction between deterministic harness evidence and live model
behavior. The research question is: can an LLM run a library?

## Workspace

Python 3.12, uv workspace, FastAPI/SQLModel services, Google ADK agents,
MCP tools, registry-hosted A2A relay, and an Angular 18 operator frontend.

- `services/`: catalog, circulation, ILL, registry.
- `agents/`: model integration, agent workflows, evaluation and benchmark runs.
- `shared/`: contracts, authentication, tracing, and observability.
- `tests/scenarios/`: deterministic scenario and invariant checks.
- `data/`: fictional seed data and network manifest.

## Workflow

Use test-driven development for behavior changes: failing test, implementation,
passing test, then the full suite. Prefer injected dependencies, typed public
interfaces, and Google-style docstrings. Keep unit tests isolated using mocks or
in-memory ASGI services; never assume a model API or localhost service is running.

```bash
uv sync --frozen --all-packages
uv run pytest -q
uv run python scripts/check_adr_links.py --strict
uv run python scripts/check_dependency_boundaries.py --strict
uv run python scripts/check_resilience_policy.py --strict
```

For frontend checks, follow `frontend/README.md`. Browser tests use a development
build with mocked API responses. Production bundles use the nginx proxy paths.

## Publication and data boundaries

Never commit real API keys, `.env` files, local databases, generated benchmark
artifacts, or real patron information. All library content and patron fixtures
must remain fictional. Review trace exports before sharing. Read `SECURITY.md`
for limitations of the local development token and demonstration identity model.

Keep operational docs in `docs/development/` and historical material in
`docs/archive/`. The portfolio validation record is
`docs/status/PUBLICATION_READINESS.md`. Follow any narrower agent guides before
changing the architecture documentation.
