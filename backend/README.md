# OpenTroop Backend

FastAPI + SQLAlchemy 2.0 + PostgreSQL backend for OpenTroop.

For full setup instructions see [docs/local-setup.md](../docs/local-setup.md).

## Quick reference

All commands run from this directory (`backend/`) using [uv](https://docs.astral.sh/uv/).

### Development

```bash
uv sync                            # install deps into .venv/
uv run uvicorn app.main:app --reload   # API on :8000 (hot-reload)
uv run pytest                      # test suite (in-memory SQLite, no DB needed)
uv run python -m mypy app scripts  # type-check
```

### Database

```bash
uv run alembic upgrade head                        # apply migrations (needs Postgres)
uv run alembic revision --autogenerate -m "msg"    # generate migration from model changes
```

Or start the full stack (Postgres + backend) from the repo root:

```bash
docker compose up --build   # backend on 127.0.0.1:8000, Postgres on 127.0.0.1:5432
```

### Data scripts

| Command | Purpose |
|---------|---------|
| `uv run provision-tenant --troop-name … --slug … --admin-first … --admin-last …` | Create a tenant + admin member + default event types; prints the tenant UUID |
| `uv run import-twh <tenant-id> <file>` | Import a TroopWebHost XML full-data export |
| `uv run reset-tenant <tenant-id>` | Clear imported data for one tenant (keeps Clerk-linked admin) |
| `uv run reset-db` | Drop all tables and re-migrate (nuclear; prompts for confirmation) |

Scripts live in `scripts/` and are registered as entry points in `pyproject.toml`.

## Architecture

```
app/
  core/         config, database, auth, permissions, tenant resolution, deps
  models/       SQLAlchemy ORM models (TrackedBase for tenant-scoped, PlatformBase for platform)
  schemas/      Pydantic v2 request/response schemas
  routers/      FastAPI route handlers
  importers/    TWH XML import logic
scripts/        CLI entry points (provision-tenant, import-twh, reset-tenant, reset-db)
alembic/        Database migrations
tests/          pytest test suite
```

Every tenant-scoped table inherits `TrackedBase`, which provides UUIDv7 primary keys,
`tenant_id`, `created_at`/`updated_at`, and `is_deleted` for offline-first sync.

## Adding a new model

1. Create `app/models/your_model.py`, subclass `TrackedBase` (or `PlatformBase` for platform-level entities)
2. Add it to `app/models/__init__.py` so it registers on `Base.metadata`
3. Run `uv run alembic revision --autogenerate -m "add your_model"` to generate the migration
4. Add schemas to `app/schemas/your_model.py` and a router to `app/routers/your_model.py`
