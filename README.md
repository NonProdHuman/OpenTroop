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

# Backend tests (from backend/)
cd backend
pip install -e ".[dev]"
pytest
```

## Data model (Phase 1)

- **Patrol** — a named unit grouping scouts.
- **Member** — scouts and adults (`member_type`), with a troop position
  (`troop_role`), BSA aquatics `swim_classification`, and optional patrol.
- **MemberRelationship** — guardian graph linking adult members to scout members.

All tables inherit `id` (UUIDv7), `tenant_id`, `created_at`, `updated_at`, and
`is_deleted` from a shared tracked base.
