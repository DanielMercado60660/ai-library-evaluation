# Quick start

Run commands from the repository root unless indicated otherwise.

## Prerequisites

- Python 3.12 and uv for the workspace and deterministic evaluation.
- Node.js 20 and npm for frontend development.
- Docker with Compose for the complete local demo.
- A Google API key only for live Gemini chat/evaluation.

## Offline regression and benchmark

```bash
uv sync --frozen --all-packages
uv run pytest -q
uv run python scripts/benchmark_run.py --suite smoke
```

The default test configuration includes `tests/`, `services/`, and
`agents/tests/`. Tests use in-memory services and mocks where configured;
no model key is required. Five legacy ILL workflow tests are explicitly skipped.

```bash
uv run python scripts/benchmark_run.py --suite scenarios --include-adk
uv run python scripts/check_adr_links.py --strict
uv run python scripts/check_dependency_boundaries.py --strict
uv run python scripts/check_resilience_policy.py --strict
```

The ADK benchmark adapter is deterministic; it does not invoke Gemini. Read the
[benchmark runbook](BENCHMARK_RUNBOOK.md) before interpreting scores.
Generated reports and databases under `artifacts/` stay out of Git.

## Docker demo

```bash
cp .env.example .env
# Edit .env: set GOOGLE_API_KEY and a MODEL_NAME available to your account.
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.demo.yml ps
```

The demo override enables `EVAL_MODE=true` on core backend services. Use
throwaway fictional databases: the reset-and-seed API replaces existing data.
Default service authentication uses the public development fixture in
`.env.example`; this is not production authentication.

### Seed the demo

After the core services are healthy, populate the hub, circulation, ILL, and
registry through their authenticated evaluation endpoints:

```bash
uv run python -c "import asyncio; from agents.eval_seeder import EvalDatabaseSeeder; print(asyncio.run(EvalDatabaseSeeder().reset_and_seed_all()))"
```

Open **http://localhost:4200**. Explore the catalog, then the Assistant,
Benchmark Runs, Analytics, and report/replay views. Model-backed interactions
may incur provider charges. An unset API key still allows offline harness work.

The four spoke catalogs are defined in Compose but require separate federation
seeding. The hub demo does not by itself populate all 635 network books. See
`scripts/seed_spoke_catalog.py` and `scripts/seed_registry_federation.py` for the
advanced provisioning path.

Stop the demo with the same Compose files:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml down
```

Named database volumes persist across restarts.

## Local process development

Install all workspace packages, then run each command in its own terminal from
the root. Give each process its own database URL.

```bash
DATABASE_URL=sqlite:///./catalog.db uv run uvicorn catalog.main:app --reload --port 8001
DATABASE_URL=sqlite:///./circulation.db uv run uvicorn circulation.main:app --reload --port 8002
DATABASE_URL=sqlite:///./ill.db uv run uvicorn ill.main:app --reload --port 8003
DATABASE_URL=sqlite:///./registry.db uv run uvicorn registry.main:app --reload --port 8004
uv run uvicorn agents.api:app --reload --port 8000 --env-file .env
```

The backend demo seeder requires `EVAL_MODE=true` in each backend process.
ILL background work also requires Redis and its worker; Compose is the easiest
way to run those dependencies together.

```bash
cd frontend
npm ci
npm start
```

Development builds call the backend ports directly. Production builds use the
nginx proxy paths supplied by the frontend container; serving a production
bundle with a plain static server does not supply that proxy.

## Frontend checks

```bash
cd frontend
npm ci
npm run build -- --configuration production
npm test -- --watch=false --browsers=ChromeHeadless
npx playwright install chromium
npm run e2e -- --grep-invert 'live backend'
```

Unit tests need Chrome/Chromium. Browser tests use a temporary development
build and mocked backend responses; they do not validate live model behavior.
Production builds fetch referenced Google Fonts during optimization.

## Ports

| Service | Port |
|---|---:|
| Frontend | 4200 |
| Agents | 8000 |
| Catalog / Circulation / ILL / Registry | 8001 / 8002 / 8003 / 8004 |
| Four spoke catalogs | 8011–8014 |
| Redis | 6379 |

For credentials and deployment limitations, read [SECURITY.md](../../SECURITY.md).
