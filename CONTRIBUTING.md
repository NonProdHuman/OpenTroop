# Contributing to OpenTroop

Thank you for helping build a better troop management tool for Scouting.

## Before You Start

- Check [open issues](../../issues) to avoid duplicating work.
- For significant changes (new models, new API surfaces, architectural decisions),
  open an issue first to discuss the approach.
- All contributions are made under the project's AGPLv3 license.

## Development Setup

The toolchain is **`uv`** (Python) and **`pnpm`** (JS/TS) — do not use `pip` or `npm`
directly. See [`README.md`](README.md) and [`docs/local-setup.md`](docs/local-setup.md)
for the full first-time walkthrough.

```bash
# Clone and enter the repo
git clone https://github.com/nonprodhuman/opentroop.git
cd opentroop

# Backend — install deps into .venv/ (from backend/)
cd backend
uv sync

# Run the test suite (no database required — uses in-memory SQLite)
uv run pytest

# Run a single test
uv run pytest tests/test_models.py::test_guardian_junction_graph

# Full stack with Postgres (from repo root)
docker compose up --build

# Generate a migration after changing a model (from backend/)
uv run alembic revision --autogenerate -m "describe what changed"
uv run alembic upgrade head
```

Frontend deps install from the repo root with `pnpm install`; run the web app with
`pnpm dev`.

## Branch and PR Conventions

- **PRs target `develop`, not `main`.** Branch from `develop`:
  `git checkout -b feat/short-description` (or `fix/short-description`).
  `develop` is promoted to `main` on release (enforced by a repo action).
- Keep PRs focused. One logical change per PR.
- All new tenant-scoped models must subclass `TrackedBase` (see `app/models/base.py`);
  cross-tenant platform entities subclass `PlatformBase`.
- **Bug fixes must include a test** that would have caught the bug — add it before the fix.
- **Non-trivial features get a spec first** in `docs/spec/` (see
  [`docs/spec/members-screen.md`](docs/spec/members-screen.md) for the expected depth).
  Skip the spec for bug fixes and small UI tweaks.
- Install and run the pre-commit hooks (`ruff`, `mypy`, `tsc`, `eslint`, gitleaks) — see
  the Pre-commit section in [`README.md`](README.md). Run `uv run pytest` locally before
  opening a PR.

## Schema / Model Rules

These are non-negotiable for the offline-sync contract:

- **No integer primary keys.** All `id` fields must be UUIDv7 (`uuid6.uuid7`).
- **Every table needs `tenant_id`** (UUID, indexed) for multi-tenant isolation.
- **Use soft deletes.** Set `is_deleted = True`; never issue physical `DELETE`.
- New models go in `app/models/`, must be added to `app/models/__init__.py`,
  and must have a corresponding schema in `app/schemas/`.

## Reporting Bugs

Open a GitHub Issue with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Python version, OS, and whether you're using Docker

## Suggesting Features

Open a GitHub Issue tagged `enhancement`. For features that touch the data model
or sync protocol, describe the domain problem first — the implementation can be
discussed from there.
