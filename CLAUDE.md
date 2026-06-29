# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See also: [`backend/CLAUDE.md`](backend/CLAUDE.md) · [`apps/web/CLAUDE.md`](apps/web/CLAUDE.md)

## Project

OpenTroop — an offline-first, mobile-first open-source replacement for TroopWebHost.
Phase 1 covers Membership/Contact Management and Event Management. Leaders must be
able to work at camps without connectivity, so the data layer is built for
background sync from day one.

**SaaS-first (primary design target).** OpenTroop is built first and foremost as a
hosted multi-tenant SaaS platform serving many troops; self-hosting (one troop, one
instance) is a supported secondary mode, not the design center. This was decided when
Clerk was chosen as the auth platform. Practical implications for all work:
- Every design decision assumes a shared platform with many tenants on it. The
  `tenant_id` partition key, subdomain tenant routing, and per-tenant rate limiting
  are first-class, not afterthoughts.
- There is a **platform/global tier above tenants** (creating tenants, inviting and
  administering tenant admins, billing/ops) that is distinct from tenant-scoped RBAC.
  Tenant creation belongs to platform (global) admins, not arbitrary signed-in users.
- New cross-tenant capabilities subclass `PlatformBase`; tenant features subclass
  `TrackedBase`. When in doubt, ask "does this row belong to one troop or to the
  platform?" — that determines the base class.
- Self-hosted mode must keep working, but where the two modes conflict, optimize for
  SaaS and degrade gracefully for single-tenant.

## Commands

### Start everything

```bash
./start.sh   # validates Clerk alignment, starts Postgres + backend + frontend
```

```bash
# Full stack (Postgres + backend) from repo root:
docker compose up --build
# Ports are bound to 127.0.0.1 via docker-compose.override.yml (auto-merged on local dev).
```

For backend-only commands see `backend/CLAUDE.md`. For frontend-only commands see `apps/web/CLAUDE.md`.

## Conventions

- **Bug fixes must include a test.** When fixing a bug, add a test that would have caught it before writing the fix.
- **New features get a spec first.** For any non-trivial new feature, write a spec in `docs/spec/` before implementing. See [`docs/spec/members-screen.md`](docs/spec/members-screen.md) for the expected format and depth. Skip the spec for bug fixes, small UI tweaks, and cases where the user explicitly asks for a direct implementation.

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

Hooks run automatically on `git commit`. All hooks use `language: system`:

| Hook | Scope | Tool |
|------|-------|------|
| `ruff`, `ruff-format` | `backend/` Python | `uv run ruff` |
| `mypy` | `backend/` Python | `uv run python -m mypy app` |
| `tsc-web` | `apps/web/` TypeScript | `pnpm exec tsc --noEmit` |
| `eslint-web` | `apps/web/` TypeScript/JSX | `pnpm exec eslint src` |
| `check-json` | whole repo JSON | pre-commit-hooks |
| `gitleaks` | whole repo | secret scanning |

Backend tools run via `uv run` (pinned to `uv.lock`); frontend tools run via
`pnpm exec` (pinned to `pnpm-lock.yaml`). Neither requires a separately-managed
pre-commit environment.

## Architecture

- **Backend** (`backend/app/`): FastAPI + SQLAlchemy 2.0 (typed `Mapped` style) +
  Pydantic v2. Config via `app/core/config.py` (pydantic-settings); engine/session
  in `app/core/database.py`.
- **Database**: PostgreSQL, migrations via Alembic (`backend/alembic/`). `env.py`
  pulls the URL from `settings` and imports `app.models` so autogenerate sees every table.
- **Frontend** (`apps/web/`): Next.js 16 (App Router) + Tailwind 4 + shadcn/ui
  (`base-nova` style) + Clerk auth. Managed via Turborepo + pnpm workspaces.
  Run with `pnpm dev` from repo root (or `pnpm --filter web dev`).
  *Note:* The web app uses Next.js Middleware (`proxy.ts`) to provide logical domain
  routing from a single deployment: the root domain (e.g. `opentroop.dev`) serves the
  landing page, the `admin` subdomain serves the platform control plane, and any other
  subdomain (e.g. `troop123.opentroop.dev`) serves that tenant's dashboard.
- **Mobile** (`apps/mobile/`): Expo (React Native) — stub, to be scaffolded once
  the web API contract stabilizes. Will share `@opentroop/api-client`.
- **API client** (`packages/api-client/`): shared TypeScript package. Types are
  generated from the FastAPI OpenAPI spec via `pnpm --filter @opentroop/api-client generate`
  (requires the backend running on `:8000`). Used by mobile; web uses hand-written types.

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
  routing), `suspended_at` (nullable; SaaS suspension marker, distinct from `is_deleted` —
  a suspended tenant still exists but is locked out of all tenant-scoped requests).
  `Tenant.id` is the value stored in `tenant_id` on all `TrackedBase` rows.
- `User` — a platform-level person identity. Fields: `email`, `display_name`,
  `platform_role`. One `User` may have `Member` records in multiple tenants. To fetch
  a user's members, query `Member.user_id == user.id`; there is no ORM backref to avoid
  a cyclic import. `platform_role` (nullable `PlatformRole` enum: `superadmin`/`support`/
  `billing`) marks the handful of **platform (global) admins** who own the SaaS control
  plane — creating tenants and administering tenant admins. It is **null for all ordinary
  users** and is entirely distinct from tenant-scoped RBAC (`Role`/`Permission`), which
  governs what a member can do inside one troop. Bootstrap the first one with
  `uv run promote-platform-admin --email <addr>` (the user must have signed in once first).
- `Identity` — a single OIDC credential bound to a `User`. Unique on
  `(issuer, provider_sub)` — the JWT `iss` + `sub` pair. Supports any compliant
  OIDC provider (Clerk, Authentik, Google, Apple, …).

**Tenant-scoped (TrackedBase):**

- `Group` — the unifying *resolvable set of members*; **folds the former `Patrol`**.
  `group_type` (`manual`/`dynamic`/`patrol`) classifies how membership is managed — a
  patrol is a `PATROL`-type group a member belongs to **at most one of** (enforced in the
  API). Membership resolves as the **union** of manual inclusions (`GroupMember`) and
  **dynamic**, rule-based members (`GroupPositionRule` — everyone holding a *position*,
  e.g. PLC = PL/SPL/ASM/SM). Groups drive event visibility (audiences) and, later, email/
  SMS distribution lists and report scoping.
- `GroupMember` — an explicit (manual) inclusion of a member in a group; also stores patrol
  membership. Soft-deletable. `GroupPositionRule` — a dynamic rule: members holding
  `position_id` belong to the group.
- `resolve_group_members(group_id, session)` in `app/core/groups.py` — walks manual + role
  rules and returns the resolved `frozenset[member_id]` (mirrors `resolve_permissions`,
  excludes soft-deleted). `member_group_ids(member_id, session)` is the inverse (which groups
  a member is in) — used by event visibility.
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
  identity once a member claims their account. `calendar_token` (nullable, unique) is
  the secret bearer token for the member's personal iCal feed (`/calendar/{token}.ics`).
  OA (Order of the Arrow) fields: `oa_member`, `oa_active` (bools), plus
  `oa_election_date`, `oa_call_out_date`, `oa_ordeal_date`, `oa_brotherhood_date`,
  `oa_vigil_date`, `oa_vigil_name`, `oa_notes` (all nullable).
- `MemberRelationship` — directional family link between any two members.
  `from_member_id` / `to_member_id` (both FKs into `members`). Relationship types:
  `parent_of`, `guardian_of` (from_member is the adult; to_member is the child/ward),
  `sibling_of` (symmetric; by convention store with the lower UUID as from_member),
  `other`. Navigate via `Member.outgoing_relationships` (relationships where this
  member is from_member) and `Member.incoming_relationships` (where this member is
  to_member).
- **RBAC is two levels deep** (see [`docs/spec/roles-rbac.md`](docs/spec/roles-rbac.md)):
  `member → Position(s) → FunctionalRole(s) → Permission(s)`. The only routine write is
  assigning a member a **position**; permissions live only on functional roles.
- `Position` (`app/models/rbac.py`) — what a member *is* (`scoutmaster`, `patrol_leader`,
  `committee_chair`). The sole assignable unit. `applies_to` (`PositionScope`:
  scout/adult/any) is a UI/validation hint; `is_system=True` marks seeded positions
  (reconfigurable, not deletable); `sort_order` orders the troop's list.
- `FunctionalRole` — a named **permission bundle** (`member-admins`, `event-admins`,
  `advancement-admins`, …). Positions map into it via `PositionFunctionalRole`.
  `is_admin=True` short-circuits to **all** permissions (the `administrators` role).
- `FunctionalRolePermission` — grants a single `Permission` to a `FunctionalRole`.
- `PositionFunctionalRole` — the many-to-many mapping (position ↔ functional role); the
  product surface, seeded with sensible defaults and edited rarely to tune governance.
- `MemberPositionAssignment` — assigns a member to a position (the routine write).
  `assigned_by_id` is the audit trail; soft-delete preserves history; a member may hold
  multiple positions (permissions union across them). There is deliberately **no** path
  to assign a functional role or raw permission directly to a member.
- `Permission` — `StrEnum` in `enums.py` listing all system capabilities, namespaced
  by domain (`member:read`, `event:create`, `role:manage`, etc.).
- `resolve_permissions(member_id, session)` in `app/core/permissions.py` — a flat 2-hop
  join `positions → functional roles → permissions`, returning a `frozenset[Permission]`.
  Short-circuits to all permissions for `is_admin` roles. Written as a union over
  permission *sources* so a future direct `PositionPermission` source drops in additively.
  Defaults are seeded at provisioning by `seed_default_rbac` (`app/core/provisioning.py`).
- `Location` — reusable named locations (name, address, phone, website_url, directions,
  description, distance_miles). Referenced by `Event.location_id`; events may also
  carry a free-text `location_notes` for one-off spots.
- `EventType` — tenant-scoped, user-customizable event type. Fields: `name`, `color`
  (hex string), `is_active`, `is_system` (seeded defaults — can disable but not delete),
  and capability flags: `tracks_service_hours`, `tracks_camping_nights`, `tracks_mileage`,
  `allow_signups`, `require_permission_slip`, `is_online`. Six defaults are seeded
  atomically on `POST /tenants/`: Meeting, Campout, Hike, Service Project, Court of
  Honor, Fundraiser. A `UniqueConstraint("tenant_id", "name")` prevents duplicate
  names within a tenant.
- `Event` — core event record (TrackedBase). Key fields: `event_type_id` (FK →
  `event_types`), `location_id` (nullable FK), `location_notes` (free text),
  `departure_location`, `return_location`, `scheduled_start`/`scheduled_end`,
  `all_day`, signup window (`signup_start`, `signup_deadline`), capacity limits
  (`signup_limit_scouts`, `signup_limit_adults`), `cost_youth`/`cost_adult` (Decimal),
  `video_conference_url`, `description`, `agenda`, `tour_permit_submitted` (nullable
  bool — None means not applicable), `attendance_taken`, `linked_event_id` (self-ref FK).
  Activity metrics (all nullable Decimal/int): `community_service_hours`,
  `conservation_hours`, `hiking_miles`, `backpacking_miles`, `paddling_miles`,
  `cycling_miles`, `water_hours`, `camping_nights`.
- `EventOrganizer` — many-to-many: `event_id` + `member_id`. Soft-deletable.
- `EventAudience` — scopes event **visibility** to Groups: `event_id` + `group_id`
  (`uq_event_audiences_event_group`). **No** audience rows = troop-wide (visible to all
  `event:read`); any rows = visible only to members of those groups, **plus** event
  managers (`event:write`) who bypass the filter. `GET /events/` filters by the caller's
  groups and `GET /events/{id}` 404s a hidden event (existence not leaked).
  `app/core/event_visibility.py` (`visibility_clause` for the list query,
  `event_visible_to_member` for one event) + `member_group_ids` in `app/core/groups.py`
  drive it; the calendar and per-member iCal feed will reuse the same rules. Audience
  CRUD: `/events/{id}/audiences` (GET/POST/DELETE).
- `EventParticipant` — RSVP + attendance per member per event. Fields: `signed_up`,
  `rsvp_status` (`RsvpStatus`: `no_response`/`going`/`declined`/`maybe`, default
  `no_response` — the member's explicit reply, distinct from the `signed_up` headcount
  flag; `declined` drives gray-out and personal-iCal omission),
  `attended` (nullable — null until `Event.attendance_taken` is set True), `guest_count`,
  `driver`, `seat_count`, `comment`, `signed_up_at`. Per-person activity overrides
  (nullable, same names as Event metrics with `_override` suffix). Permission slip:
  `permission_slip_submitted`, `electronic_permission`, `electronic_permission_at`,
  `electronic_permission_by_id` (FK → members), `electronic_permission_signature`.
  Setting `attended` via PATCH is gated: returns 409 if `Event.attendance_taken` is False.

Enums live in `app/models/enums.py` and are shared between ORM models and schemas.

### Auth architecture

- **JWT validation** (`app/core/auth.py`): `decode_token` fetches the JWKS from
  `AUTH_JWKS_URI`, validates RS256/ES256 signatures, and checks `aud` only when
  `AUTH_AUDIENCE` is set (omit for providers that don't use `aud`).
- **User provisioning**: `get_or_create_user` maps validated `(iss, sub)` claims to a
  `User` + `Identity` row pair, creating both atomically on first login.
- **Tenant resolution** (`app/core/tenant.py`): `get_tenant_id` resolves the tenant
  from the request subdomain first (`troop123.opentroop.app` → slug lookup), then
  falls back to the `X-Tenant-ID` header (raw UUID → DB validation). Nested
  subdomains are rejected to prevent Host-header spoofing. A **suspended** tenant
  (`Tenant.suspended_at` set) is rejected with 403 on both resolution paths.
- **FastAPI dependencies** (`app/core/deps.py`): `TenantDep`, `DbDep`,
  `CurrentUserDep` — wire these into route handlers to enforce auth and tenant scope.
  `require(permission)` — dependency factory used as `dependencies=[Depends(require(Permission.X))]`
  on each route; resolves the caller's `Member` in the current tenant and checks
  their effective permission set via `resolve_permissions()`. Raises 403 if the user
  has no Member row in this tenant or lacks the required permission.
  `get_platform_admin` / `PlatformAdminDep` — gates the SaaS control plane: requires the
  caller's `User.platform_role` to be set (any value), independent of any tenant. Raises
  403 for ordinary users.
- **Platform control plane** (`app/routers/platform.py`, prefix `/platform`, every route
  gated by `PlatformAdminDep`): the SaaS control plane.
  - `POST /platform/tenants` — **provision a tenant**: atomically creates the Tenant, an
    **unclaimed** founding admin Member (`user_id` null, named/emailed via the request body),
    the default RBAC (positions, functional roles, mapping) with the founder holding the
    Administrator position, and the six default event types. Returns the
    tenant plus a 7-day invite token for the founder. The provisioning admin does **not**
    become a member of the new tenant.
  - `GET /platform/tenants`, `GET /platform/tenants/{id}` — list / inspect tenants.
  - `POST /platform/tenants/{id}/suspend` · `/unsuspend` — set/clear `suspended_at`
    (idempotent); a suspended tenant rejects all tenant-scoped requests.
  - `GET /platform/tenants/{id}/admins` — members holding the is_admin role.
  - `POST /platform/tenants/{id}/admins` — invite another admin (unclaimed Member + claim token).
  - `DELETE /platform/tenants/{id}/admins/{member_id}` — revoke admin; 409 if it would remove
    the tenant's last administrator, 404 if the member isn't an admin here.
  - `GET /platform/admins` — list users holding any `platform_role` (any platform admin may view).
  - `POST /platform/admins` · `DELETE /platform/admins/{user_id}` — grant/revoke a platform role
    by email / user id. **Superadmin only** (`SuperadminDep` / `get_superadmin` in `deps.py`):
    `support`/`billing` are read-only here so they can't self-escalate. Grant 404s if the email
    has never signed in; revoke 409s on the last remaining superadmin.

  The shared building blocks live in `app/core/provisioning.py` (`provision_tenant`,
  `invite_admin_member`, `seed_default_rbac` / `get_administrator_position`,
  `seed_default_event_types` + `DEFAULT_FUNCTIONAL_ROLES` / `DEFAULT_POSITIONS` /
  `DEFAULT_EVENT_TYPES`). The `provision-tenant` CLI is the separate dev/self-host path: it
  writes the DB directly, bypassing the API gate, and auto-links the single signed-in `User`
  as founder.
- **Invite/claim flow** (`app/core/invite.py`): `create_invite_token` / `decode_invite_token`
  use HS256 (signed with `APP_SECRET`) to produce 7-day claim tokens. Tokens are minted
  either by tenant provisioning (for the founder) or by an admin calling
  `POST /members/{id}/invite`; the invitee signs in via OIDC then calls `POST /auth/claim`
  with the token to link their `User.id` to the `Member` row.
- **iCal calendar feed** (`app/routers/calendar.py`, `app/core/ical.py`): a member's
  personal calendar. `GET /calendar/{token}.ics` is **unauthenticated by design** — the
  unguessable `Member.calendar_token` is the credential (calendar apps can't do OAuth);
  it resolves the member by token, 404s on unknown/rotated tokens and suspended/deleted
  tenants, and emits RFC 5545 VEVENTs for events the member can see
  (`event_visibility`) minus ones they've **declined** (`rsvp_status`). The token is
  minted/rotated via `POST`/`DELETE /calendar/subscription` (authenticated, current
  member). The feed is audience-based (no manager bypass) — it's *my* calendar, not a
  management view.
