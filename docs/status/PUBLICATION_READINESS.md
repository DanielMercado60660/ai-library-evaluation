# Publication readiness

Verified October 7, 2026. This record describes the portfolio snapshot, not a
production certification or live model benchmark.

## Validation

| Check | Result |
|---|---|
| Locked uv workspace sync | Passed with `--frozen --all-packages` |
| Python regression suite | 953 passed, 5 skipped; 6 existing SQLAlchemy warnings |
| Angular production build | Passed; existing bundle/CommonJS warnings |
| Frontend unit tests | 32 passed in ChromeHeadless |
| Mocked browser suite | 30 passed in Chromium |
| Architecture checks | ADR links, dependency boundaries, resilience policy passed |
| Deterministic smoke benchmark | 12 passed; report, JUnit, trace, compliance output generated |
| Full deterministic scenario run with ADK adapter | 241 passed; trace, compliance and forensic artifacts generated |
| Demo Compose configuration | Validated with `docker compose ... config --quiet` |
| Secrets audit | Public source snapshot and all reachable publication commits passed Gitleaks with zero findings |

The browser suite now uses development API URLs and one worker with its
lightweight static preview server. A default `env.js` avoids a missing runtime
configuration file in local previews. The full pytest configuration includes
agent tests alongside services and scenarios.

The ILL source-holdings path rejects a verified ISBN miss rather than creating
a request the source cannot satisfy. Its existing in-process federation
regression test failed before the fix and passed afterward. The local
availability unit test now mocks the catalog boundary explicitly. Active
performance and recovery documents were restored after the documentation
reorganization broke four regression checks. The catalog validator now locates
seed files relative to its checkout rather than a hardcoded personal path; a
relocation regression test failed before that fix and passed afterward.

## Publication boundary

An API credential was found in the original project's older Git history.
The public repository starts from a fresh source snapshot, excluding that
history, local environment files, databases, caches, and runtime artifacts.
The original local archive is preserved. Credentials exposed in old commits
still need revocation or rotation by their owner.

CI runs the full Python suite, frontend checks, deterministic scenario artifact
generation, and a redacted Gitleaks scan over all reachable Git history.

## Limits

- Docker configuration was parsed, but container startup was not exercised:
  the local Docker daemon was unavailable.
- No paid model inference or live Gemini quality evaluation was performed.
- Deterministic ADK adapter scores and mocked UI tests are platform evidence.
- The four spoke catalogs require separate federation provisioning.
- Development service authentication, patron identity selection, and permissive
  outage behavior require further hardening before real-world deployment.
- Old status and archive documents describe earlier work; this record is the
  current publication checkpoint.
