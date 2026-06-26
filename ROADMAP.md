# OpenTroop Roadmap

OpenTroop is a community-driven, offline-first replacement for TroopWebHost.
This document describes the six capability pillars and how they build on each other.
Granular tasks are tracked via GitHub Issues and Milestones.

OpenTroop is designed to run in two modes:

- **Self-hosted** — a single troop runs their own instance. The operator is the
  troop leader. All configuration (SMTP credentials, etc.) lives in `.env`.
  No platform dependency; zero per-email cost if using G Suite or M365 as a relay.
- **SaaS** — a hosted platform serving many troops (target: up to 200+). Each troop
  is a tenant. Sending infrastructure is shared but tenant-scoped; per-tenant rate
  limits and "from" addresses prevent one troop from affecting others' deliverability.

Both modes are supported by the same codebase. The `tenant_id` on every database row
is the foundation; notification and configuration systems follow the same pattern.

---

## Guiding Principles

- **Offline-first always.** Every feature must work without a network connection
  and synchronize gracefully when connectivity returns.
- **Data model before UI.** Schema changes are expensive; invest in getting the
  domain model right before building surfaces on top of it.
- **Analyze before building.** For complex domains (advancement, events, recharter),
  export real data from TroopWebHost and Scoutbook first and let that shape the model.
- **Easy migration path.** A troop switching from TroopWebHost should be able to
  import their existing data with minimal friction. This is a first-class feature.

---
## Next Features to address:
- Dynamic Groups
- Event RSVP and Permission workflow
- Tenant Data Access and full RLS enforcement (docs/spec/tenant-data-access.md)
- Hosting and deployment pipeline (docs/spec/hosting-and-deployment.md)


## Capability Pillars

### Pillar 1 — Roster & Relationships *(active)*

The load-bearing foundation. Everything else depends on a correct, sync-capable
membership model.

- [x] `TrackedBase` mixin: UUIDv7 PK, `tenant_id`, timestamps, soft-delete
- [x] `Member` (type + role + BSA swim classification), `MemberRelationship` guardian graph;
      `Patrol` folded into the general `Group` model (see **Groups & Audiences** below)
- [x] Pydantic v2 schemas, Alembic setup, pytest suite on SQLite
- [x] Initial Alembic migration (requires live Postgres)
- [x] FastAPI CRUD endpoints for Patrol, Member, MemberRelationship
- [x] Role-based access control — permission guards wired to all route handlers;
      `require(permission)` dependency checks the caller's Member + role hierarchy
- [x] Auth (JWT; consider Scoutbook SSO as a future option)
- [x] OA (Order of the Arrow) fields on Member — `oa_member`, `oa_active`, election/
      call-out/ordeal/brotherhood/vigil dates, vigil name, notes
- [x] TroopWebHost XML full-dump import (roster + events) — `app/importers/twh.py`
      CLI: `uv run python import_twh.py <tenant-id> <export.xml>` from `backend/`
- [x] Multi-tenant provisioning — `POST /tenants/` bootstraps Tenant + founding admin
      Member + administrators Role atomically; invite/claim flow links existing
      roster entries to login accounts via signed tokens
- [x] Platform (global) admin tier — `User.platform_role` gates the SaaS control plane;
      `POST /tenants/` is platform-admin-only and creates an *unclaimed* founding admin
      Member invited by email (the provisioning admin doesn't join the troop);
      `promote-platform-admin` CLI bootstraps the first global admin
- [x] Platform control-plane API (`/platform/*`, platform-admin only) — provision/list/
      inspect tenants; suspend/unsuspend (suspended tenants are locked out of tenant-scoped
      requests); list, invite, and revoke tenant admins (last-admin guard). Shared
      provisioning helpers in `app/core/provisioning.py`
- [x] Platform control-plane **UI** — global management console at `/platform` (admin-gated via
      `platform_role`): tenants list, provision-tenant dialog, tenant detail with suspend/unsuspend
      and admin invite/revoke; sidebar link shown only to platform admins
- [x] Platform-admin management — `GET/POST/DELETE /platform/admins` (grant/revoke gated to
      superadmins; last-superadmin guard) + `/platform/admins` console screen; promotes platform
      admins through the UI instead of the `promote-platform-admin` CLI alone
- [ ] Scoutbook member export import (BSA recharter format)
- [ ] Automated invite email delivery (depends on Pillar 5 notification infra) — until then
      provisioning returns the invite token for manual/out-of-band delivery

#### Groups & Audiences *(foundational — folds Patrol)*

A **Group** is a named, *resolvable set of members* — the single primitive behind
event visibility, email/SMS distribution lists, and report scoping. Rather than
hard-coding "patrol" as the only axis to scope things, every audience is a group,
and a patrol is just one kind of group. TWH's strength is exactly this: dynamic
*and* manual groups (e.g. a PLC of everyone holding a leadership role) that drive
both messaging and visibility. This is the layer those features consume, so it
lands before them (data model before UI).

- [x] `Group` model (`name`, `description`, `group_type`, `color`, `is_system`)
      replacing the standalone `Patrol` model — a patrol is a `PATROL`-type group
- [x] **Manual** membership — explicit `GroupMember` rows (also stores patrol
      membership; a member belongs to at most one `PATROL` group)
- [x] **Dynamic** membership — rule-based; v1 is role-driven (`GroupRoleRule`),
      so the PLC resolves to everyone holding PL / SPL / ASM / SM
- [x] `resolve_group_members(group_id, session)` — unions manual + rule-derived
      members (mirrors `resolve_permissions`); the one function every consumer calls
- [x] Groups API (`/groups`) — CRUD, manual membership, role rules, resolved members
- [x] TWH importer maps `Patrol` → `PATROL` group and each scout's patrol → `GroupMember`
- [x] Migration folds `patrols` + `members.patrol_id` into the group tables
- [ ] Groups management UI (sidebar "Groups", replaces "Patrols") — spec: `docs/spec/groups-screen.md`
- [ ] **Dynamic group rule editor** — UI for defining `GroupRoleRule` entries that drive
      dynamic group membership. Phase 1: role-based rules (members holding role X belong to
      group Y). Phase 2: additional dimensions — `member_type`, `membership_status`,
      patrol-of-patrols. Requires a rule-builder component; spec deferred until the
      Groups screen UI is complete and UX patterns for rule composition are clearer.
- [ ] Additional dynamic rule dimensions (member_type, membership_status, patrol-of-patrols)

### Pillar 2 — Multi-Tenant Isolation & Data Access

The `tenant_id` on every `TrackedBase` row is the foundation of both deployment modes,
but isolation is currently enforced only by **hand-written `tenant_id ==` predicates on
every query** (~200 across 13 routers). The failure mode is "forget one and that
endpoint leaks" — already observed once in review. This cross-cutting workstream makes
isolation automatic and default-on, backstopped at the database, and explicit in the UI.
The three items are independently shippable but share one current-tenant source of truth.

- [~] **Tenant-scoped data access layer** — a request-scoped current-tenant `ContextVar`
      plus a SQLAlchemy `do_orm_execute` listener that auto-applies the `tenant_id`
      filter to every `TrackedBase` read (including relationship loads) and a
      `before_flush` hook that stamps `tenant_id` on writes. Route code stops carrying the
      predicate; cross-tenant access becomes an explicit, greppable `unscoped()` opt-out
      used only by the platform control plane. Behavior-preserving, lands incrementally.
      Spec: [`docs/spec/tenant-data-access.md`](docs/spec/tenant-data-access.md).
      **Status:** engine shipped and active (`app/core/database.py` listeners +
      `app/core/tenant_context.py`, `unscoped()` escape hatch); the GUC is already
      stamped per transaction. Remaining: finish removing the ~200 hand-written
      `tenant_id ==` predicates from the routers (~21 still present across 10 routers)
      and wrap every cross-tenant `TrackedBase` access (platform plane, auth memberships)
      in `unscoped()` — a prerequisite for enforcing RLS below.
- [ ] **Postgres Row-Level Security (RLS)** — the database-layer backstop: a restricted
      non-owner app role, a per-transaction `SET LOCAL app.current_tenant` GUC, and
      `USING` + `WITH CHECK` policies (`FORCE ROW LEVEL SECURITY`) generated per
      `TrackedBase` table from the model registry. Catches any query that bypasses the app
      layer; especially valuable for the mobile sync pull/push paths (a leaked row in a
      sync payload persists on-device). Tested by a small Postgres-backed tier
      (SQLite can't exercise RLS) run **per-PR** via a CI service container against a
      migrated DB — including a policy-completeness introspection test; the SQLite suite
      stays the fast default. Spec: [`docs/spec/postgres-rls.md`](docs/spec/postgres-rls.md).
  - [ ] **RLS enforcement cutover** — the sequenced plan to move RLS from installed-but-
        dormant to actually enforcing without breaking the app or migrations: finish the
        redundant-predicate cleanup, put every cross-tenant path on `unscoped()`, wire
        physically separate app/admin connection pools (`opentroop_app` RLS-enforced vs
        `opentroop_admin` `BYPASSRLS`, Alembic on the owner), then flip
        `FORCE ROW LEVEL SECURITY`. Also covers the
        autogenerate blindspot (new tables need RLS+policy+grants by hand) and the
        non-reproducible `__subclasses__()` introspection. Spec:
        [`docs/spec/rls-enforcement-rollout.md`](docs/spec/rls-enforcement-rollout.md).
  - [ ] **Split the platform control plane into its own service** *(later — at real
        multi-tenant launch, not now)* — lift `/platform` + provisioning + the
        `opentroop_admin` engine into a separate FastAPI entrypoint/Cloud Run service on
        `admin.opentroop.app`, so the tenant-facing process holds no `BYPASSRLS`
        capability. Stays a deployment flag (`MOUNT_PLATFORM`), not a code fork —
        self-hosted keeps running one all-in-one process. See "Deployment topology" in
        [`docs/spec/rls-enforcement-rollout.md`](docs/spec/rls-enforcement-rollout.md).
- [ ] **Tenant switcher UI + `GET /auth/memberships`** — a user who is a `Member` of
      several troops picks the active tenant from a pulldown; the app shows exactly one
      tenant at a time (never a merged view). New auth-only, cross-tenant-for-one-user
      endpoint lists the caller's memberships; the web app replaces the build-time
      `NEXT_PUBLIC_TENANT_ID` constant with runtime active-tenant state, and every React
      Query key is scoped by tenant so switching refetches cleanly. Makes "active tenant"
      first-class — also the basis for on-device store partitioning in the mobile client.
      Spec: [`docs/spec/tenant-switcher.md`](docs/spec/tenant-switcher.md).


### Pillar 3 — Events & Calendar

Event types differ meaningfully. Campouts carry permit numbers and capacity limits.
Merit badge clinics have prerequisites. Courts of Honor tie into advancement data.
Model events generically with typed metadata rather than one-size-fits-all fields.

- [x] Analyze TroopWebHost event export format before designing the model
- [x] `Location` model — reusable named locations (address, phone, website, notes)
      referenced by events rather than inlining address fields per-event
- [x] Core `Event` model (name, type, dates, location FK, capacity, tenant-scoped)
- [x] Event types — tenant-customizable `EventType` model; 6 defaults seeded on
      provisioning (Meeting, Campout, Hike, Service Project, Court of Honor, Fundraiser);
      capability flags drive field visibility (tracks_mileage, tracks_camping_nights, etc.)
- [x] Event organizers (which members are responsible for running the event)
- [ ] Event shifts (multiple time slots within one event — deferred; redesigning for
      universal sign-up slots beyond TWH's shift model)
- [x] RSVP / attendance tracking per member — `EventParticipant` with `signed_up`,
      `attended`, per-person activity overrides, and electronic permission slip fields
- [x] Event costs (separate youth/adult pricing — `cost_youth` / `cost_adult`)
- [ ] Digital permission slips (fillable forms attached to events; parent signature flow)
- [ ] Parent-authorized RSVP & Permission flow — parental approval/permission slip integration for specific event types (e.g. high-adventure campouts, out-of-state trips) before RSVP is confirmed
- [ ] Health form collection and storage (per-event or per-member)
- [~] Calendar view — month grid done (`apps/web/.../events`, List/Calendar toggle);
      weekly/day views (calendar library swap) still pending
- [x] Event visibility / audiences — `EventAudience` links events to Groups
      (empty = troop-wide); the list + detail endpoints filter by the viewer's group
      membership (managers bypass), backing patrol-only events. Calendar + iCal reuse
      the same `app/core/event_visibility.py` rules.
- [x] RSVP status (going / declined / maybe / no-response) on `EventParticipant` —
      explicit member reply (distinct from `signed_up`); drives gray-out in the app and
      omission from personal iCal feeds (consumed by the iCal feed below)
- [x] Per-member iCal subscription feeds — tokenized `.ics` (`GET /calendar/{token}.ics`,
      `webcal://`) honoring group visibility and excluding declined events; subscribable
      from Apple/Google Calendar. Subscribe/rotate via `/calendar/subscription`.
- [ ] Event notifications (email; push via mobile apps later)

### Pillar 4 — Advancement & Requirements

The most complex domain. BSA advancement has a strict hierarchy
(program → rank → requirements → sub-requirements), merit badges with counselor
sign-offs, and Eagle project tracking. Scoutbook is the authoritative record;
this pillar should sync with it, not replace it.

- [ ] Analyze Scoutbook advancement export format before designing the model
- [ ] BSA rank and requirement hierarchy (Scout → Eagle; Cub Scouts separate program)
- [ ] Merit badge catalog (current list; periodic BSA updates)
- [ ] Requirement completion tracking per member
- [ ] Merit badge counselor management
- [ ] Eagle project proposal and approval workflow
- [ ] Scoutbook two-way sync (import completions; export sign-offs)
- [ ] Advancement report generation (for boards of review, courts of honor)

### Pillar 5 — Communications & Reports

UI-heavy and legally sensitive (minors, health data). Build after the data
model is stable enough to query reliably.

#### Notification infrastructure (prerequisite for all messaging features)

A 40-scout troop reaches ~115 recipients per send (scouts × 2 parents + adult
leaders). One weekly newsletter plus routine patrol and event emails is
~1,400 emails/month per troop; at 200 troops that is ~280,000/month in aggregate.
Infrastructure must handle this without synchronous request handlers and without
vendor lock-in.

- [ ] `NotificationService` abstraction — `EmailBackend` and `SMSBackend` protocols;
      the rest of the app calls the protocol, never a vendor SDK directly
- [ ] **Email backends** (configure via `EMAIL_BACKEND` env var):
  - `smtp` — uses any SMTP relay; ideal for self-hosters with G Suite / M365
  - `resend` — [Resend](https://resend.com) for small SaaS deployments
    (50k emails/month on paid plan); excellent deliverability, simple SDK
  - `ses` — AWS SES for large SaaS deployments (~$0.10/1k; ~$28/month at 200 troops)
- [ ] **SMS backends** (configure via `SMS_BACKEND` env var; optional feature):
  - `twilio` — most reliable North American delivery
  - `telnyx` — drop-in alternative, ~30% cheaper than Twilio
- [ ] Async send queue (ARQ or Celery) — bulk sends run in background workers,
      not request handlers; includes per-tenant rate limiting for SaaS deployments
- [ ] Retry and dead-letter handling — failed sends requeue with exponential backoff;
      permanently failed messages land in a dead-letter store for operator review
- [ ] Bounce and complaint webhooks — vendor webhooks map back to the sending tenant;
      hard bounces auto-set `Member.email_bounced`; spam complaints trigger review
- [ ] `Member` opt-out fields — `email_opt_out` (bool) and `email_bounced` (bool);
      the send queue skips opted-out and bounced addresses; required for CAN-SPAM
- [ ] `TroopSettings` model — per-tenant notification config (custom from-address,
      optional bring-your-own SMTP credentials); falls back to platform default in
      SaaS mode, or to the global `.env` config in self-hosted mode
- [ ] Push notifications via Firebase FCM — free, covers iOS and Android through a
      single API; complements email rather than replacing it (some parents won't
      install the app; email is always the fallback)

#### Messaging features

- [ ] Group-targeted announcements (email + optional SMS) — distribution lists are
      Groups; recipients resolve via `resolve_group_members` (replaces the former
      troop-/patrol-only scoping)
- [ ] Event-triggered notifications: RSVP reminders, permission slip requests,
      last-minute cancellations
- [ ] Weekly digest / newsletter template
- [ ] SMS opt-in flow — explicit consent required; store consent timestamp and
      source on `Member`
- [ ] Unsubscribe / preference centre — parents can manage their own email and SMS
      preferences without contacting the scoutmaster

#### Reports

- [ ] Report builder: roster by patrol, advancement summary, swim classification list
- [ ] PDF export for reports and permission slips
- [ ] Parent/guardian contact directory (scoped by guardian links)
- [ ] Medical form storage with expiration tracking (BSA Annual Health & Medical Record)
- [ ] TroopWebHost-compatible data export (migration path for troops leaving TWH)

#### Natural Language Reports (Text-to-SQL)

Troop reporting needs are too varied to cover with a fixed set of UI screens —
a leader asking "which scouts have not yet completed their swimming requirement
before summer camp?" is a different query than "what merit badges were earned
between June and August?" Rather than trying to build a form for every edge case,
a Text-to-SQL layer lets any leader ask questions in plain English.

**How it works:**

1. Leader types a natural language question in the app.
2. The backend sends the question to an LLM along with: (a) the current database
   schema (table names, column names, types, and relationships), and (b) a small
   set of representative sample rows per table (no PII beyond what is needed for
   the model to understand the shape of the data).
3. The LLM returns a SQL `SELECT` query — no writes, no DDL.
4. The backend executes that query against a **read-only replica connection string**
   (separate from the write connection) scoped to the requesting `tenant_id`.
5. Results are rendered as a table or exported to CSV/PDF.

**Safety constraints:**

- Read-only Postgres role on the replica — the database enforces this, not
  application code.
- All queries are appended with a `WHERE tenant_id = :tenant_id` guard before
  execution to prevent cross-tenant data leakage.
- Query execution timeout and row-count cap prevent runaway queries.
- The generated SQL is logged per-request for audit and debugging.

**Tasks:**

- [ ] Read-only Postgres replica connection string support (env var `DATABASE_URL_READONLY`)
- [ ] Schema introspection endpoint — serializes `Base.metadata` into a prompt-friendly
      description (table → columns → types → FK relationships)
- [ ] Sample data extractor — pulls N anonymized rows per table for LLM context
- [ ] LLM query generation service (`POST /api/reports/natural-language`) — sends
      schema + sample data + question to Claude; returns raw SQL
- [ ] SQL safety layer — parse and validate that the returned query is a single
      `SELECT`; inject `tenant_id` filter; enforce timeout + row cap
- [ ] Query execution and result formatting (table view + CSV export)
- [ ] PDF export for natural language query results
- [ ] UI: natural language query input with result table and export controls
- [ ] Prompt library — pre-written example questions to help leaders get started
      ("scouts due for rank advancement", "attendance by patrol last 90 days", etc.)

---

### Pillar 6 — Web Application Shell & Navigation

The web app is scaffolded with a **flat** sidebar (Members, Groups, Events, Import,
Settings). As the pillars above grow into many pages, the shell needs structure. The
information architecture — the three navigation shells, and the rule for sidebar
sub-navigation vs. in-page tabs — is specified in
[`docs/spec/navigation.md`](docs/spec/navigation.md). In short:

- **Authenticated app** — left sidebar; collapsible groups for *destinations*, in-page
  tabs for *lenses on the same data*. This is the backbone.
- **Platform console** — existing top-tab shell at `/platform` (global admins). As-is.
- **Public troop website** — a separate, troop-branded shell for unauthenticated
  visitors and a logged-in member view; *edited* from inside the app (see Content
  Management below). Not a sidebar section.

App-shell work not already tracked under a pillar:

- [x] Collapsible sidebar with sub-navigation (hybrid IA — `app-sidebar.tsx`)
- [ ] **Current-member + permissions endpoint** — a tenant-scoped
      `GET /auth/session` (resolved from the JWT + `X-Tenant-ID`) returning the
      caller's `Member` and effective `permissions[]` (via `resolve_permissions`),
      plus a `usePermissions()` / `has(permission)` hook. Today the frontend only
      has `/auth/me` (the platform `User` + `platform_role`) — it has **no tenant
      permissions**, so nav and buttons can't be gated. Client-side gating is UX
      only; the backend `require()` stays the real enforcement. Spec:
      `docs/spec/session-permissions.md`. **Prerequisite** for:
- [ ] Permission-filtered nav & action buttons — hide sections (e.g. Money without
      `finance:read`) and actions (Add Member without `member:write`) the caller
      can't use; extends the `isPlatformAdmin` pattern in `app-sidebar.tsx`
- [ ] **Home / dashboard** landing (announcements feed, upcoming events, my action
      items) — replaces today's redirect-to-Members default
- [ ] **Roles & permissions** management UI (RBAC backend exists; no surface yet)
- [ ] **Bulk editing** — bulk medical-form dates and other mass member updates
      (Members → Bulk edit)
- [ ] **Parent ("My Family") views** — permission-scoped views inside Members and
      Advancement so a parent manages their own scouts' info and advancement; not a
      separate section
- [ ] **Resources** — troop document & link library
- [ ] **Photo gallery** — event-linked albums (Events → Gallery)

## Additional Domains (Future / Undesigned)

New domains surfaced for parity but not yet modelled. Per "data model before UI," each
needs a schema spec (a `TrackedBase` subclass design) before any surface is built.

### Money / Treasury

Treasurer tools: per-scout account balances, transactions (dues, fundraiser credits,
event charges), invoices, and budget tracking. Previously listed only as a Phase-1
scope *exclusion*; it belongs on the roadmap as a later phase.

- [ ] Data-model spec (accounts, ledger entries, charges tied to events)
- [ ] Scout account balances + transaction history
- [ ] Invoices / statements; budget views

### Inventory / Equipment

Track troop-owned equipment and who it is checked out to.

- [ ] Data-model spec (equipment items, assignments/check-out, condition/history)
- [ ] Equipment registry + per-member assignment / check-out flow

### Content Management / Public Website (Pillar 5 adjacency)

OpenTroop should double as the troop's public web presence — like TWH, serving content
to both authenticated members and anonymous visitors, with visibility varying by
audience. Pages are simple but their content varies per troop, so this is a lightweight
CMS, not a page builder.

- [ ] Data-model spec (content blocks/pages, public vs. member-only visibility)
- [ ] Public shell + per-troop theming
- [ ] In-app editing surface (Settings → Website content)

---

## Mobile Applications

Native iOS and Android apps are the offline-sync clients for Pillars 1–4.
They are not a separate phase — they should be developed in parallel once the
API contract for each pillar stabilizes.

- [ ] API design review for mobile consumption (REST vs. GraphQL decision)
- [ ] Offline data layer design (local SQLite + sync protocol) — if a device ever caches
      more than one tenant, the local store must be partitioned by active tenant
      (server-side RLS stops at the backend; see **Multi-Tenant Isolation & Data Access**)
- [ ] iOS app (Swift / SwiftUI)
- [ ] Android app (Kotlin / Jetpack Compose)
- [ ] Push notification integration

---

## What OpenTroop Is Not (Scope Boundaries)

- Not a replacement for Scoutbook as the BSA's authoritative advancement record.
  OpenTroop syncs with Scoutbook; it does not compete with it.
- Not a financial management system (dues, fundraiser accounting) in Phase 1.
- Not a national BSA membership registration system.
