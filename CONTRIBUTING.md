# Contributing

Start with the [quick start](docs/development/QUICK_START.md),
[architecture](docs/architecture/OVERVIEW.md), and
[fictional world](docs/world/HANNO_WORLD_BIBLE.md).

## Working on a change

1. Keep the change focused and add a failing test for behavioral changes.
2. Implement the change using typed interfaces and injected dependencies.
3. Use in-memory databases, ASGI transports, or explicit mocks in tests.
   Tests should not require a running service or model API key.
4. Run `uv run pytest -q` from the repository root. This includes services,
   scenarios, and agents.
5. For UI changes, run the production build, unit tests, and mocked browser
   suite described in the frontend README.

All catalog and scenario content must remain fictional. If a test deliberately
mentions real-world literature to probe a guardrail, make that purpose explicit.
Do not add real patron data, API keys, local databases, or generated run folders.

## Before a pull request

```bash
uv run python scripts/check_adr_links.py --strict
uv run python scripts/check_dependency_boundaries.py --strict
uv run python scripts/check_resilience_policy.py --strict
gitleaks git --redact=100 --log-opts='--all' .
```

Explain the behavior changed and validation performed. Keep live model results
separate from deterministic fixture results, and document the model and run
configuration when reporting an evaluation.
