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
apps/web/      Next.js 16 · Tailwind 4 · shadcn/ui · Clerk auth
apps/mobile/   Expo (React Native) — stub, to be scaffolded
backend/       FastAPI app, ORM models, Pydantic schemas, Alembic, tests
packages/      Shared TypeScript packages (api-client)
```

## Quick start

```bash
./start.sh
```

Validates that your Clerk configuration is consistent between frontend and backend, starts Postgres via Docker, runs the backend with uvicorn, and launches the Next.js dev server. See [docs/local-setup.md](docs/local-setup.md) for the full first-time setup walkthrough.

## Local development

**Frontend** — requires [pnpm](https://pnpm.io) and Node 18+:

```bash
npm install -g pnpm
pnpm install                            # install all workspace deps
cp apps/web/.env.local.example apps/web/.env.local   # add Clerk keys
pnpm dev                                # start web app on :3000
```

**Backend** — requires [uv](https://docs.astral.sh/uv/) and Python 3.12:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # install uv once
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

Hooks cover trailing whitespace, YAML/TOML/JSON validation, secret scanning
(gitleaks), Python linting/formatting + types (ruff, mypy — pinned via `uv.lock`),
and frontend type-checking + linting (`tsc`, `eslint` — pinned via `pnpm-lock.yaml`).

## Data model (Phase 1)

**Platform-level (global, no tenant scope):**
- **Tenant** — one row per troop; its `id` is the `tenant_id` on every other table.
- **User** — a platform login identity (spans tenants; one person can be a member in multiple troops).
- **Identity** — one OIDC provider credential per User (Google, Apple, passkeys, etc.).

**Tenant-scoped (every row carries `tenant_id`):**
- **Patrol** — a named unit grouping scouts.
- **Member** — scouts and adults, with BSA `swim_classification`, optional patrol, OA fields, and a nullable link to a `User` login account.
- **MemberRelationship** — guardian/parent/sibling graph linking members.
- **Role / RolePermission / RoleMembership** — two-tier RBAC: functional groups hold permissions; positions inherit from groups.
- **MemberRoleAssignment** — assigns a member to a role, with a soft-delete audit trail.
- **Location** — reusable named locations (address, phone, directions) referenced by events.
- **EventType** — tenant-customizable event categories with capability flags (`tracks_camping_nights`, `allow_signups`, etc.); six defaults seeded on provisioning.
- **Event** — core event record with dates, location, costs, activity metrics, signup window, and capacity limits.
- **EventOrganizer** — which members are running a given event.
- **EventParticipant** — per-member RSVP, attendance, activity overrides, and permission slip tracking.

All tables inherit `id` (UUIDv7), `created_at`, `updated_at`, and `is_deleted` from a shared base.
Tenant-scoped tables additionally carry `tenant_id`.

## Authentication

OpenTroop validates standard OIDC JWTs — any compliant provider works.
See **[docs/auth-provider-setup.md](docs/auth-provider-setup.md)** for step-by-step
Clerk (SaaS) and Authentik (self-hosted) setup.

## Deployment

See **[docs/deployment.md](docs/deployment.md)** for a full guide.
The recommended production setup is **Google Cloud Run + Cloud SQL**, which
starts at ~$10–15/month and scales to hundreds of troops without rearchitecting.
