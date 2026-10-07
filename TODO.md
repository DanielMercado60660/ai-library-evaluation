# TODO — v2.5 Docker Testing Issues

## Status
v2.5 implementation is complete (Dockerfile, nginx, CI, tests, PDF export all done).
Docker builds and all services start healthy. Backend tests (649) and frontend tests (32) pass.
**Currently debugging frontend-in-Docker issues found during live testing.**

---

## Issue 1: Frontend shows "Failed to load books" / "No patrons found"

**Symptom:** Browser at `http://localhost:4200` shows error messages even though backend services have data.

**Root cause (FIXED in code, needs re-test):**
The production environment had empty string URLs for all services. nginx only proxied
`/chat`, `/benchmark`, `/health`, `/admin` to the agents backend — no proxy rules for
catalog, circulation, ILL, or registry.

**Fix applied:**
- `frontend/nginx.conf` — Added 4 upstream blocks and `/api/catalog/`, `/api/circulation/`,
  `/api/ill/`, `/api/registry/` location blocks that strip the prefix and proxy to correct backends.
- `frontend/src/environments/environment.production.ts` — Changed catalog/circulation/ill/registry
  URLs from `''` to `/api/catalog`, `/api/circulation`, `/api/ill`, `/api/registry`.

**Verification (from curl):**
- `curl http://localhost:4200/api/catalog/books` returns 150 books
- `curl http://localhost:4200/api/circulation/patrons` returns 10 patrons
- All 5 service health checks return correct individual service responses
- The JS bundle contains `/api/catalog` (confirmed via grep on served main.js)

**What to check tomorrow:**
- Hard refresh the browser (Cmd+Shift+R) — old JS bundle may be cached
- Try incognito window to rule out browser cache
- Check browser DevTools Network tab — are requests going to `/api/catalog/books`?
- If still failing, check browser console for CORS or auth errors

---

## Issue 2: Chat always returns "I'm having trouble processing that"

**Symptom:** All chat messages get the fallback error response.

**Root cause (FIXED, needs re-test):**
The model name `gemini-3.0-flash` doesn't exist in the Gemini API. The correct name
is `gemini-3-flash-preview` (Gemini 3 uses `-preview` suffix, no dots in version).

**Fix applied:**
- `.env` — Added `MODEL_NAME=gemini-3-flash-preview`
- `agents/src/agents/config.py` — Default changed to `gemini-3-flash-preview`
- `agents/src/agents/models/factory.py` — Fallback changed
- `agents/src/agents/api.py` — Model catalog fallback changed to `gemini-3-flash-preview` and `gemini-3-pro-preview`
- `docker-compose.yml` — Default changed
- `tests/scenarios/test_model_memory_contract.py` — Contract assertion updated
- `frontend/.../run-config-dialog.component.ts` — Fallback model options updated

**Verification (from curl after fix):**
Chat returned a proper response about elephant books from the catalog.

**What to check tomorrow:**
- After `docker compose up -d`, test: `curl -X POST http://localhost:4200/chat -H "Content-Type: application/json" -H "X-Service-Token: ${SERVICE_AUTH_TOKEN}" -d '{"message":"hello","active_patron":{"id":"P001","name":"Test","role":"patron"}}'`
- If still failing, check `docker compose logs agents --tail 20` for model errors
- Verify MODEL_NAME is set: `docker exec ai-library-agents-1 env | grep MODEL`

---

## Issue 3: Frontend healthcheck was "unhealthy"

**Root cause (FIXED):**
Alpine's `wget` tries IPv6 `::1` first, but nginx only binds IPv4 `0.0.0.0:80`.

**Fix applied:**
`docker-compose.yml` healthcheck changed from `http://localhost:80/` to `http://127.0.0.1:80/`.

---

## Quick Start for Tomorrow

```bash
cd ai-library

# Start everything
docker compose up --build -d

# Wait ~30s for all services to be healthy
docker compose ps

# Verify services
curl http://localhost:4200/health                        # agents health
curl http://localhost:4200/api/catalog/health             # catalog health
curl http://localhost:4200/api/catalog/books?limit=2      # books (needs X-Service-Token header)

# Test chat
curl -X POST http://localhost:4200/chat \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: ${SERVICE_AUTH_TOKEN}" \
  -d '{"message":"Search for books about elephants","active_patron":{"id":"P001","name":"Test","role":"patron"}}'

# Open browser
open http://localhost:4200

# Check logs if issues
docker compose logs agents --tail 30
docker compose logs frontend --tail 30

# Run tests (no Docker needed)
cd frontend && npx ng test --watch=false --browsers=ChromeHeadless  # 32 tests
cd .. && uv run pytest -q                                            # 649 tests
```

---

## Documentation Cleanup Tasks

After the recent documentation reorganization, these items remain:

### Status Docs Refresh
The following status documents are out of date relative to current implementation:
- [ ] `docs/status/PROJECT_STATUS.md` — needs alignment with v2.1+ reality
- [ ] `docs/status/V2_1_EXECUTION_PLAN.md` — may be complete/superseded
- [ ] `docs/status/VERSION_LADDER_PROPOSAL.md` — roadmap needs updating
- [ ] `docs/status/FULLY_FINISHED_TARGET_STATE.md` — rewrite using `ProjectGoal.md` as base

### Architecture Reference Review
Review `docs/architecture/` for quality and alignment with `ProjectGoal.md`:
- [ ] `OVERVIEW.md` — does it match the research vision?
- [ ] `DATA_MODEL.md` — accurate reflection of current schemas?
- [ ] `A2A_PROTOCOL.md` — protocol docs match implementation?
- [ ] `AGENTS.md` — agent architecture aligned with ADK usage?
- [ ] `SECURITY.md` — security model accurately documented?
- [ ] `SERVICES.md` — service topology correct?
- [ ] `adr/` — ADRs still relevant? Any missing decisions?

### World Docs
- [ ] `docs/world/` — verify still accurate (likely unchanged, but review)

---

## Remaining `gemini-3.0-flash` References (non-breaking)

These are in test fixtures and e2e test data — they use the old model name as test data values,
not as actual API calls. They won't cause runtime failures but should be updated for consistency:

- `tests/fixtures/golden/run-index-v1.5.json` (golden fixture)
- `artifacts/runs/index.json` (historical run data)
- `artifacts/runs/run-*/benchmark-report.json` (historical report)
- `tests/scenarios/test_contract_compatibility.py:108` (asserts fixture data)
- `agents/tests/integration/test_benchmark_run_lifecycle.py` (test request bodies)
- `agents/tests/unit/test_eval_report.py` (test data)
- `agents/tests/unit/test_benchmark_orchestrator_benchmark.py` (test data)
- `frontend/e2e/*.spec.ts` (e2e test data)
- `frontend/src/app/core/services/run.service.spec.ts` (unit test data)
