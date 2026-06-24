# OpenTroop Roadmap

OpenTroop is a community-driven, offline-first replacement for TroopWebHost.
This document describes the four capability pillars and how they build on each other.
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

## Capability Pillars

### Pillar 1 — Roster & Relationships *(active)*

The load-bearing foundation. Everything else depends on a correct, sync-capable
membership model.

- [x] `TrackedBase` mixin: UUIDv7 PK, `tenant_id`, timestamps, soft-delete
- [x] `Patrol`, `Member` (type + role + BSA swim classification), `MemberRelationship` guardian graph
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
- [ ] Scoutbook member export import (BSA recharter format)
- [x] Multi-tenant provisioning — `POST /tenants/` bootstraps Tenant + founding admin
      Member + administrators Role atomically; invite/claim flow links existing
      roster entries to login accounts via signed tokens
- [x] Platform (global) admin tier — `User.platform_role` gates the SaaS control plane;
      `POST /tenants/` is platform-admin-only and creates an *unclaimed* founding admin
      Member invited by email (the provisioning admin doesn't join the troop);
      `promote-platform-admin` CLI bootstraps the first global admin
- [ ] Platform control-plane API (`/platform/*`) — list/suspend tenants; invite, list,
      and grant/revoke tenant admins from the global tier (UI: a global management console)
- [ ] Automated invite email delivery (depends on Pillar 4 notification infra) — until then
      provisioning returns the invite token for manual/out-of-band delivery

### Pillar 2 — Events & Calendar

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
- [ ] Packing lists — deferred (feature creep risk before UI exists)
- [ ] Digital permission slips (fillable forms attached to events; parent signature flow)
- [ ] Health form collection and storage (per-event or per-member)
- [ ] Calendar view (monthly/weekly; iCal export)
- [ ] Event notifications (email; push via mobile apps later)

### Pillar 3 — Advancement & Requirements

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

### Pillar 4 — Communications & Reports

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

- [ ] Troop-wide and patrol-scoped announcements (email + optional SMS)
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

## Mobile Applications

Native iOS and Android apps are the offline-sync clients for Pillars 1–3.
They are not a separate phase — they should be developed in parallel once the
API contract for each pillar stabilizes.

- [ ] API design review for mobile consumption (REST vs. GraphQL decision)
- [ ] Offline data layer design (local SQLite + sync protocol)
- [ ] iOS app (Swift / SwiftUI)
- [ ] Android app (Kotlin / Jetpack Compose)
- [ ] Push notification integration

---

## Near-Term Priorities (Next Steps)

Pillars 1 and 2 are complete at the API layer. The web app shell is scaffolded
(`apps/web/` — Next.js 16, Tailwind 4, shadcn/ui, Clerk auth, sidebar layout).

1. **Members screen** — searchable/filterable roster list + inline detail panel;
   the highest-impact screen for demonstrating the UX difference from TroopWebHost.
2. **Events screen** — event list and detail view; reuses the same data-table patterns.
3. **Attendance screen** — the key field UX moment; optimistic updates, fast tap targets.
4. **Pillar 3 analysis** — export Scoutbook advancement data from a real troop before
   designing the advancement model; let the data shape the schema.
5. **Scoutbook member import** — BSA recharter XML format (complement to the TWH importer).
6. **TroopWebHost-compatible export** — round-trip migration path for troops leaving TWH.

---

## What OpenTroop Is Not (Scope Boundaries)

- Not a replacement for Scoutbook as the BSA's authoritative advancement record.
  OpenTroop syncs with Scoutbook; it does not compete with it.
- Not a financial management system (dues, fundraiser accounting) in Phase 1.
- Not a national BSA membership registration system.
