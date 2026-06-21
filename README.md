# OpenTroop

A modern, mobile-first, open-source replacement for TroopWebHost.

**Phase 1 scope:** Membership / Contact Management and Event Management.

OpenTroop is built **offline-first** so leaders can keep working at camps without
cellular service. Every table is designed for background synchronization
(client-generatable UUIDv7 keys, per-row timestamps, soft-delete tombstones) and
is partitioned by `tenant_id` for future multi-tenant SaaS.

## Architecture

| Layer        | Technology |
|--------------|------------|
| Backend      | Python · FastAPI · SQLAlchemy 2.0 |
| Database     | PostgreSQL · Alembic migrations |
| Frontend     | Next.js · Tailwind CSS · shadcn/ui |
| Offline      | Native iOS / Android apps with local caching + sync |
| Orchestration| docker-compose (db + backend) |

```
backend/    FastAPI app, ORM models, Pydantic schemas, Alembic, tests
frontend/   Next.js client (scaffolded in a later phase)
```

## Quick start

```bash
# Run the full stack
docker compose up --build
```

## Local development

[uv](https://docs.astral.sh/uv/) manages the Python environment. Install it once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then from `backend/`:

```bash
uv sync               # create .venv/ and install all deps
uv run pytest         # run the test suite (no database needed)
uv run uvicorn app.main:app --reload   # start the API on :8000
```

### Pre-commit hooks

```bash
# Install pre-commit once (uses uv's global tool layer)
uv tool install pre-commit --with pre-commit-uv

# Wire hooks into git (once per clone)
pre-commit install

# Or run manually
pre-commit run --all-files
```

Hooks cover trailing whitespace, YAML/TOML validation, secret scanning (gitleaks),
and Python linting/formatting via ruff (pinned to the version in `uv.lock`).

## Data model (Phase 1)

- **Patrol** — a named unit grouping scouts.
- **Member** — scouts and adults (`member_type`), with a troop position
  (`troop_role`), BSA aquatics `swim_classification`, and optional patrol.
- **MemberRelationship** — guardian graph linking adult members to scout members.

All tables inherit `id` (UUIDv7), `tenant_id`, `created_at`, `updated_at`, and
`is_deleted` from a shared tracked base.
