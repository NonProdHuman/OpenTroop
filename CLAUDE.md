# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OpenTroop — an offline-first, mobile-first open-source replacement for TroopWebHost.
Phase 1 covers Membership/Contact Management and Event Management. Leaders must be
able to work at camps without connectivity, so the data layer is built for
background sync from day one.

## Commands

All backend commands run from `backend/`:

```bash
pip install -e ".[dev]"          # install backend + dev (pytest) deps
pytest                           # run the test suite (in-memory SQLite, no DB needed)
pytest tests/test_models.py::test_guardian_junction_graph   # run a single test
alembic revision --autogenerate -m "msg"   # create a migration from model changes
alembic upgrade head             # apply migrations (needs a live Postgres)
uvicorn app.main:app --reload    # run the API locally

# Full stack (Postgres + backend) from repo root:
docker compose up --build
```

## Architecture

- **Backend** (`backend/app/`): FastAPI + SQLAlchemy 2.0 (typed `Mapped` style) +
  Pydantic v2. Config via `app/core/config.py` (pydantic-settings); engine/session
  in `app/core/database.py`.
- **Database**: PostgreSQL, migrations via Alembic (`backend/alembic/`). `env.py`
  pulls the URL from `settings` and imports `app.models` so autogenerate sees every table.
- **Frontend** (`frontend/`): reserved for Next.js + Tailwind + shadcn/ui; native
  iOS/Android apps will own offline caching + sync. Not yet scaffolded.

### Sync-aware schema contract (critical)

Every table MUST inherit `TrackedBase` (`app/models/base.py`), which supplies:

- `id` — **UUIDv7** primary key (`uuid6.uuid7`), client-generatable offline and
  time-ordered for index locality. Never use sequential integer PKs.
- `tenant_id` — UUID partition key for multi-tenant SaaS; required on every row.
- `created_at` / `updated_at` — timezone-aware, auto-managed (conflict signals).
- `is_deleted` — soft-delete tombstone; deletes are logical, not physical.

The dialect-agnostic SQLAlchemy `Uuid` type lets the Postgres-targeted models run
unmodified on SQLite, which is how the test suite stays DB-free.

### Domain model (`app/models/`)

- `Patrol` — named unit; one-to-many to `Member`.
- `Member` — scouts and adults. Two orthogonal enums: `member_type`
  (scout/adult) vs `troop_role` (scoutmaster, ASM, SPL, treasurer, none, …).
  Aquatics via `swim_classification` (BSA: nonswimmer/beginner/swimmer).
- `MemberRelationship` — junction implementing the guardian graph; both
  `adult_id` and `scout_id` are FKs into `members`. Navigate via
  `Member.guardian_links` (a scout's adults) and `Member.dependent_links`
  (an adult's scouts).

Enums live in `app/models/enums.py` and are shared between ORM models and schemas.

### Conventions

- ORM models in `app/models/`, Pydantic schemas in `app/schemas/` (kept separate).
  Each resource exposes `*Base` / `*Create` / `*Update` / `*Read` schemas;
  `*Read` inherits `TrackedRead` and uses `from_attributes=True`.
- New models: subclass `TrackedBase`, then add the class to `app/models/__init__.py`
  so it registers on `Base.metadata` for tests and Alembic autogenerate.
