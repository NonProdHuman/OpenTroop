# 0007. httpx2 as the backend HTTP client

- **Status:** Accepted
- **Date:** 2026-07-05

## Context

The backend makes outbound HTTP calls to third-party APIs — Resend for
transactional email (`app/core/notifications.py::ResendEmailBackend`) and the
Expo Push Service for mobile notifications (`ExpoPushBackend`). These paths are
in the critical path of member communications, so the client library needs
timely security updates and a maintained release cadence.

The project originally used `httpx`. Upstream `httpx` has seen limited activity;
Pydantic assumed stewardship of the codebase and continues it under a new
distribution name, **`httpx2`** ("the next generation HTTP client" — HTTP/1.1 +
HTTP/2, sync and async APIs, same public surface). Because the package name is
unusual, a contributor skimming `import httpx2 as httpx` could reasonably
mistake it for a typo or a typosquat and "fix" it back to `httpx`. It is
neither — it is the deliberately chosen, actively maintained successor. This ADR
exists so that assumption is written down once and not re-litigated on every
dependency review or supply-chain scan.

## Decision

We use **`httpx2`** as the backend's HTTP client, pinned in
`backend/pyproject.toml` (`httpx2>=0.28`) and locked in `backend/uv.lock`. Call
sites import it as `import httpx2 as httpx` so the idiomatic `httpx.post(...)` /
`httpx.HTTPError` surface is preserved and only the dependency, not the code,
changed.

## Consequences

- We inherit Pydantic's maintenance and security-update cadence rather than
  depending on a stalled upstream.
- The API is drop-in compatible with `httpx`, so existing call sites and any
  future ones read exactly as they would against `httpx`; the `as httpx` alias
  keeps that intentional.
- **Cost:** the `httpx2` name is younger and less recognizable than `httpx`.
  Automated supply-chain / typosquat tooling and human reviewers may flag it —
  this ADR (plus the note in `backend/CLAUDE.md`) is the answer to point them at.
  Anyone tempted to rewrite the import to `httpx` should read this first.

## Alternatives considered

- **Stay on `httpx`.** Rejected: limited upstream activity means slower security
  fixes on a library in the critical path of outbound comms.
- **`requests` / `aiohttp` / `urllib3`.** Rejected: `requests` has no async
  support (the app is async-first); switching to `aiohttp`/`urllib3` would mean
  rewriting call sites for no benefit `httpx2` doesn't already provide.
