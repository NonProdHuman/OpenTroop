# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

OpenTroop — an offline-first, mobile-first open-source replacement for TroopWebHost.
Phase 1 covers Membership/Contact Management and Event Management. Leaders must be
able to work at camps without connectivity, so the data layer is built for
background sync from day one.

## Commands

All backend commands run from `backend/`. Use `uv` — never `pip` directly.
Requires **Python 3.12**.

```bash
uv sync                          # install backend + dev deps into .venv/
uv run pytest                    # run the test suite (in-memory SQLite, no DB needed)
uv run pytest tests/test_models.py::test_parent_child_relationship  # run a single test
uv run python -m mypy app        # type-check
uv run alembic revision --autogenerate -m "msg"   # create a migration from model changes
uv run alembic upgrade head      # apply migrations (needs a live Postgres)
uv run uvicorn app.main:app --reload  # run the API locally

# Full stack (Postgres + backend) from repo root:
docker compose up --build
# Ports are bound to 127.0.0.1 via docker-compose.override.yml (auto-merged on local dev).
```

## Pre-commit hooks

`pre-commit` is a repo-wide tool managed via `uv tool`, not a project dependency.
Install it once globally, then wire it into git:

```bash
# One-time global install (pre-commit-uv makes hook env creation faster)
uv tool install pre-commit --with pre-commit-uv

# One-time per clone — installs the git hooks
pre-commit install

# Run all hooks manually against every file
pre-commit run --all-files
```

Hooks run automatically on `git commit`. The `ruff`, `ruff-format`, and `mypy` hooks
all use `language: system` so they invoke their tools via `uv run` from `backend/`,
keeping versions in sync with `uv.lock` rather than a separately-pinned pre-commit
environment.

## Architecture

- **Backend** (`backend/app/`): FastAPI + SQLAlchemy 2.0 (typed `Mapped` style) +
  Pydantic v2. Config via `app/core/config.py` (pydantic-settings); engine/session
  in `app/core/database.py`.
- **Database**: PostgreSQL, migrations via Alembic (`backend/alembic/`). `env.py`
  pulls the URL from `settings` and imports `app.models` so autogenerate sees every table.
- **Frontend** (`frontend/`): reserved for Next.js + Tailwind + shadcn/ui; native
  iOS/Android apps will own offline caching + sync. Not yet scaffolded.

### Sync-aware schema contract (critical)

Every tenant-scoped table MUST inherit `TrackedBase` (`app/models/base.py`), which supplies:

- `id` — **UUIDv7** primary key (`uuid6.uuid7`), client-generatable offline and
  time-ordered for index locality. Never use sequential integer PKs.
- `tenant_id` — UUID partition key for multi-tenant SaaS; required on every row.
- `created_at` / `updated_at` — timezone-aware, auto-managed (conflict signals).
- `is_deleted` — soft-delete tombstone; deletes are logical, not physical.

**Cross-tenant platform entities** (Tenant, User, Identity) use `PlatformBase`
instead. `PlatformBase` has the same `id`, timestamps, and `is_deleted` as
`TrackedBase` but **no `tenant_id`**.

The dialect-agnostic SQLAlchemy `Uuid` type lets the Postgres-targeted models run
unmodified on SQLite, which is how the test suite stays DB-free.

### Domain model (`app/models/`)

**Platform-level (PlatformBase, no tenant_id):**

- `Tenant` — one row per troop. Fields: `name`, `slug` (unique; used for subdomain
  routing). `Tenant.id` is the value stored in `tenant_id` on all `TrackedBase` rows.
- `User` — a platform-level person identity. Fields: `email`, `display_name`. One
  `User` may have `Member` records in multiple tenants. To fetch a user's members,
  query `Member.user_id == user.id`; there is no ORM backref to avoid a cyclic import.
- `Identity` — a single OIDC credential bound to a `User`. Unique on
  `(issuer, provider_sub)` — the JWT `iss` + `sub` pair. Supports any compliant
  OIDC provider (Clerk, Authentik, Google, Apple, …).

**Tenant-scoped (TrackedBase):**

- `Patrol` — named unit; one-to-many to `Member`.
- `Member` — scouts and adults. Key enums: `member_type` (scout/adult),
  `membership_status` (active/inactive/alumni — distinct from `is_deleted`; alumni
  records remain visible to leaders for history while `is_deleted=True` purges the
  record from sync payloads entirely), `swim_classification` (BSA: nonswimmer/beginner/
  swimmer). Extended fields: full mailing address, date_of_birth, nickname,
  name_suffix, medical form dates (ab/c), swim_date, allergies,
  dietary_restrictions, two emergency contacts, notes.
  `bsa_id` is **nullable** — non-registered parents and family contacts are
  valid roster members without a BSA number. The canonical identifier is always
  `id` (UUIDv7). A partial unique index `uix_members_tenant_bsa_id` on
  `(tenant_id, bsa_id) WHERE bsa_id IS NOT NULL` prevents duplicate registrations
  within a troop while permitting multiple null values. It is declared in
  `Member.__table_args__` and created by the initial Alembic migration.
  `user_id` (nullable FK → `users.id`) links the roster record to the platform
  identity once a member claims their account.
- `MemberRelationship` — directional family link between any two members.
  `from_member_id` / `to_member_id` (both FKs into `members`). Relationship types:
  `parent_of`, `guardian_of` (from_member is the adult; to_member is the child/ward),
  `sibling_of` (symmetric; by convention store with the lower UUID as from_member),
  `other`. Navigate via `Member.outgoing_relationships` (relationships where this
  member is from_member) and `Member.incoming_relationships` (where this member is
  to_member).
- `Role` — tenant-scoped named role. Two kinds in practice: **functional groups**
  (`event_admin`, `member_admin`, `advancement_admin`, `finance_admin`) that hold
  permissions directly, and **positions** (`scoutmaster`, `patrol_leader`, etc.) that
  inherit from functional groups via `RoleMembership`. `is_system=True` marks seeded
  roles that can't be deleted. `is_admin=True` bypasses all permission checks
  (reserved for the `administrators` role).
- `RolePermission` — grants a single `Permission` enum value to a `Role`.
- `RoleMembership` — records that a position role is a member of a functional group.
  `group_role_id` (the functional group) / `member_role_id` (the position). Members
  assigned to a position inherit all permissions of the group transitively.
- `MemberRoleAssignment` — assigns a member to any role (position or functional group
  directly). `assigned_by_id` provides an audit trail. Soft-delete preserves history.
  A member may hold multiple roles simultaneously.
- `Permission` — `StrEnum` in `enums.py` listing all system capabilities, namespaced
  by domain (`member:read`, `event:create`, `role:manage`, etc.).
- `resolve_permissions(member_id, session)` in `app/core/permissions.py` — walks
  `MemberRoleAssignment` → `RoleMembership` transitively (cycle-safe) and returns a
  `frozenset[Permission]`. Short-circuits to all permissions for `is_admin` roles.

Enums live in `app/models/enums.py` and are shared between ORM models and schemas.

### Auth architecture

- **JWT validation** (`app/core/auth.py`): `decode_token` fetches the JWKS from
  `AUTH_JWKS_URI`, validates RS256/ES256 signatures, and checks `aud` only when
  `AUTH_AUDIENCE` is set (omit for providers that don't use `aud`).
- **User provisioning**: `get_or_create_user` maps validated `(iss, sub)` claims to a
  `User` + `Identity` row pair, creating both atomically on first login.
- **Tenant resolution** (`app/core/tenant.py`): `get_tenant_id` resolves the tenant
  from the request subdomain first (`troop123.opentroop.org` → slug lookup), then
  falls back to the `X-Tenant-ID` header (raw UUID → DB validation). Nested
  subdomains are rejected to prevent Host-header spoofing.
- **FastAPI dependencies** (`app/core/deps.py`): `TenantDep`, `DbDep`,
  `CurrentUserDep` — wire these into route handlers to enforce auth and tenant scope.
  `require(permission)` — dependency factory used as `dependencies=[Depends(require(Permission.X))]`
  on each route; resolves the caller's `Member` in the current tenant and checks
  their effective permission set via `resolve_permissions()`. Raises 403 if the user
  has no Member row in this tenant or lacks the required permission.
- **Tenant provisioning** (`POST /tenants/`): creates Tenant + founding admin Member
  + administrators Role atomically. No tenant context required; only `CurrentUserDep`.
- **Invite/claim flow** (`app/core/invite.py`): `create_invite_token` / `decode_invite_token`
  use HS256 (signed with `APP_SECRET`) to produce 7-day claim tokens. An admin calls
  `POST /members/{id}/invite`; the invitee signs in via OIDC then calls
  `POST /auth/claim` with the token to link their `User.id` to the `Member` row.

### Conventions

- ORM models in `app/models/`, Pydantic schemas in `app/schemas/` (kept separate).
  Each resource exposes `*Base` / `*Create` / `*Update` / `*Read` schemas.
  `*Read` for tenant-scoped models inherits `TrackedRead`; for platform models it
  inherits `PlatformRead`. Both use `from_attributes=True`.
- New tenant-scoped models: subclass `TrackedBase`, then add the class to
  `app/models/__init__.py` so it registers on `Base.metadata` for tests and Alembic
  autogenerate.
- New platform-level models: subclass `PlatformBase` instead (no `tenant_id`).
