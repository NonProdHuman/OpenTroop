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
pytest tests/test_models.py::test_parent_child_relationship  # run a single test
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
- `Member` — scouts and adults. Key enums: `member_type` (scout/adult),
  `membership_status` (active/inactive/alumni — distinct from `is_deleted`; alumni
  records remain visible to leaders for history while `is_deleted=True` purges the
  record from sync payloads entirely), `troop_role` (scoutmaster, ASM, SPL,
  treasurer, none, … — convenience denormalization; authoritative history goes in a
  future `LeadershipHistory` table), `swim_classification` (BSA: nonswimmer/beginner/
  swimmer). Extended fields: full mailing address, date_of_birth, nickname,
  name_suffix, medical form dates (ab/c), swim_date, allergies,
  dietary_restrictions, two emergency contacts, notes.
  `bsa_id` is **nullable** — non-registered parents and family contacts are
  valid roster members without a BSA number. The canonical identifier is always
  `id` (UUIDv7). A partial unique index on `(tenant_id, bsa_id) WHERE bsa_id
  IS NOT NULL` prevents duplicate registrations within a troop while permitting
  multiple null values; add this in the first Alembic migration.
- `MemberRelationship` — directional family link between any two members.
  `from_member_id` / `to_member_id` (both FKs into `members`). Relationship types:
  `parent_of`, `guardian_of` (from_member is the adult; to_member is the child/ward),
  `sibling_of` (symmetric; by convention store with the lower UUID as from_member),
  `other`. Navigate via `Member.outgoing_relationships` (relationships where this
  member is from_member) and `Member.incoming_relationships` (where this member is
  to_member).

Enums live in `app/models/enums.py` and are shared between ORM models and schemas.

### Conventions

- ORM models in `app/models/`, Pydantic schemas in `app/schemas/` (kept separate).
  Each resource exposes `*Base` / `*Create` / `*Update` / `*Read` schemas;
  `*Read` inherits `TrackedRead` and uses `from_attributes=True`.
- New models: subclass `TrackedBase`, then add the class to `app/models/__init__.py`
  so it registers on `Base.metadata` for tests and Alembic autogenerate.
