# Security

This is a local research alpha using fictional books, patrons, and transactions.
Keep the demo on a trusted machine. The shared development service token and
browser-selected patron identity are demonstration mechanisms; they do not
provide production authentication or authorization. Several service outage
paths permit requests to continue, so this platform should not manage real
patron records or finances without additional hardening.

## Credentials

- Copy `.env.example` to `.env` and set credentials only on your machine.
- `.env` variants, private keys, service-account files, databases, and runtime
  artifacts are excluded from Git and Docker build contexts.
- The Google API key belongs in the agents service, never in frontend code.
- CI runs offline tests with an empty Google API key and scans Git history
  with Gitleaks.
- Traces and benchmark exports can contain prompts and tool payloads. Review
  them before sharing. Runtime output is intentionally excluded from the repo.

## Reporting

Use GitHub's private vulnerability reporting feature when available. Otherwise,
open an issue describing the affected area without including credentials or
sensitive payloads. Never post a working key in an issue, commit, or screenshot.
If a credential is exposed, revoke or rotate it at its provider before removing
it from files and history; deleting a line alone does not invalidate a key.
