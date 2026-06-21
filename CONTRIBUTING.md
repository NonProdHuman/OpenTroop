# Contributing to OpenTroop

Thank you for helping build a better troop management tool for Scouting.

## Before You Start

- Check [open issues](../../issues) to avoid duplicating work.
- For significant changes (new models, new API surfaces, architectural decisions),
  open an issue first to discuss the approach.
- All contributions are made under the project's AGPLv3 license.

## Development Setup

```bash
# Clone and enter the repo
git clone https://github.com/nonprodhuman/opentroop.git
cd opentroop

# Backend — install with dev dependencies
cd backend
pip install -e ".[dev]"

# Run the test suite (no database required — uses in-memory SQLite)
pytest

# Run a single test
pytest tests/test_models.py::test_guardian_junction_graph

# Full stack with Postgres (from repo root)
docker compose up --build

# Generate a migration after changing a model
cd backend
alembic revision --autogenerate -m "describe what changed"
alembic upgrade head
```

## Branch and PR Conventions

- Branch from `main`: `git checkout -b feat/short-description` or `fix/short-description`
- Keep PRs focused. One logical change per PR.
- All new models must subclass `TrackedBase` (see `app/models/base.py`).
- Add or update tests in `backend/tests/` for any model or schema change.
- Run `pytest` locally before opening a PR.

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
