# OpenTroop Roadmap

OpenTroop is a community-driven, offline-first replacement for TroopWebHost.
This document is the **strategic map**: the six capability pillars, why they exist,
and the order they build in. It is intentionally high-level.

**Granular, actionable work lives in [GitHub Issues](../../issues), grouped by
[Milestone](../../milestones) (one milestone per pillar).** The roadmap answers
*"why, and in what order"*; issues answer *"what's actionable now, and who's on it."*
When those two disagree, the issues are the source of truth for task state — this file
is not a checklist to tick off.

> **New contributor?** Start with [`CONTRIBUTING.md`](CONTRIBUTING.md), then browse
> the [`good first issue`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
> and [`help wanted`](../../issues?q=is%3Aissue+is%3Aopen+label%3A%22help+wanted%22) labels.

OpenTroop runs in two modes from one codebase:

- **SaaS (primary)** — a hosted platform serving many troops (target: 200+). Each troop
  is a tenant; sending infrastructure is shared but tenant-scoped, with per-tenant rate
  limits and "from" addresses so one troop can't affect another's deliverability.
- **Self-hosted** — a single troop runs their own instance. The operator is the troop
  leader; all configuration lives in `.env`. No platform dependency.

The `tenant_id` on every `TrackedBase` row is the foundation of both modes; notification
and configuration systems follow the same pattern.

---

## Guiding Principles

- **Offline-first always.** Every feature must work without a network connection and
  synchronize gracefully when connectivity returns.
- **Data model before UI.** Schema changes are expensive; get the domain model right
  before building surfaces on top of it. New domains need a `docs/spec/` design first.
- **Analyze before building.** For complex domains (advancement, events, recharter),
  export real data from TroopWebHost and Scoutbook first and let that shape the model.
- **Easy migration path.** A troop switching from TroopWebHost should import their
  existing data with minimal friction. This is a first-class feature.

---

## How to read the pillar status

Each pillar below carries a one-line **Status** and a short summary of what has shipped
and what is next. The next-up work is enumerated as issues under that pillar's milestone
— follow the link rather than expecting a checklist here.

| Status | Meaning |
|--------|---------|
| ✅ **Foundational — shipped** | Core is built and in use; only follow-on items remain |
| 🚧 **Active** | Being worked now; the near-term backlog is filed as issues |
| 🔜 **Next up** | Sequenced to start soon; specs may exist, issues being filed |
| 🧊 **Future** | Deferred / undesigned; needs a spec before implementation |

---

## Pillar 1 — Roster & Relationships

**Status: ✅ Foundational — shipped.** · Milestone: *Pillar 1 — Roster & Relationships*

The load-bearing foundation: a correct, sync-capable membership model. Everything else
depends on it.

**Shipped:** `TrackedBase` (UUIDv7 PK, `tenant_id`, timestamps, soft-delete); `Member`
(type/status/BSA swim classification, OA fields, full contact + medical fields);
`MemberRelationship` guardian graph; two-level RBAC (`Position → FunctionalRole →
Permission`) with `require()` guards on every route and privilege-escalation guardrails
on position assignment (only admins may grant admin/`role:manage`-conferring positions;
last-admin protection); OIDC/JWT auth with invite-claim
flow; multi-tenant provisioning and the platform (global) admin tier + control-plane API
and UI; **Groups & Audiences** (the `Group` primitive that folds Patrol — manual +
dynamic rule-based membership, `resolve_group_members`, dynamic rule editor); TWH XML
full-dump importer (roster, events, leadership-as-position-terms, source provenance);
automated invite-email delivery (rides the Pillar 5 notification service); baseline
member access — every member holds a seeded "Member" position granting read access,
with self/family contact+medical edit for positionless parents and scouts
([`baseline-member-access.md`](docs/spec/baseline-member-access.md)).

**Next up (see issues):** Scoutbook member-export import (BSA recharter format).

---

## Pillar 2 — Multi-Tenant Isolation & Data Access

**Status: ✅ Foundational — shipped.** · Milestone: *Pillar 2 — Multi-Tenant Isolation*

`tenant_id` on every `TrackedBase` row is the foundation; isolation is now defense-in-depth
rather than per-query predicates.

**Shipped:** request-scoped current-tenant `ContextVar` + SQLAlchemy listeners that
auto-scope every `TrackedBase` read and stamp `tenant_id` on writes (`unscoped()` is the
greppable cross-tenant escape hatch); Postgres Row-Level Security backstop with
per-transaction GUC and generated policies, tested by a Postgres-backed CI tier; the RLS
enforcement cutover (separate `opentroop_app` / `opentroop_admin` pools, `FORCE ROW LEVEL
SECURITY`); tenant switcher UI + `GET /auth/memberships` with per-tenant React Query keys.
Specs: [`tenant-data-access.md`](docs/spec/tenant-data-access.md),
[`postgres-rls.md`](docs/spec/postgres-rls.md),
[`rls-enforcement-rollout.md`](docs/spec/rls-enforcement-rollout.md),
[`tenant-switcher.md`](docs/spec/tenant-switcher.md).

**Next up (see issues):** *(later — at real multi-tenant launch)* split the platform
control plane into its own service on `admin.opentroop.app` so the tenant-facing process
holds no `BYPASSRLS` capability. Stays a deployment flag (`MOUNT_PLATFORM`), not a fork.

---

## Pillar 3 — Events & Calendar

**Status: 🚧 Active.** · Milestone: *Pillar 3 — Events & Calendar*

Event types differ meaningfully — model events generically with typed metadata rather
than one-size-fits-all fields.

**Shipped:** `Location`, `EventType` (six seeded defaults + capability flags), core
`Event` model and organizers; `EventParticipant` RSVP/attendance with per-person activity
overrides; `RsvpStatus` (going/declined/maybe/no-response); youth/adult costs; event
visibility / audiences (`EventAudience` → Groups, managers bypass); the RSVP + parental
electronic-permission workflow, including the event edit page and RSVP admin tab;
per-member tokenized iCal subscription feeds; month-grid calendar (List/Calendar toggle);
event-triggered email notifications — creation, cancellation, and permission-slip
requests, riding the Pillar 5 notification service; **event photo galleries** (the event
is the album; Cloudflare R2 object storage with presigned upload/read, per-tenant storage
quotas, moderation — web + mobile clients; ADR 0011).
Specs: [`event-edit.md`](docs/spec/event-edit.md),
[`event-rsvp-permission.md`](docs/spec/event-rsvp-permission.md),
[`member-event-create.md`](docs/spec/member-event-create.md).

**Next up (see issues):** health-form collection & storage; permission-slip PDF
export; multi-day event bars in the month view. Deferred: universal sign-up slots
(the redesign superseding TWH's event-shift model).

---

## Pillar 4 — Advancement & Requirements

**Status: 🚧 Active — core shipped.** · Milestone: *Pillar 4 — Advancement*

The most complex domain. BSA advancement has a strict hierarchy
(program → rank → requirements → sub-requirements), merit badges with counselor
sign-offs, and Eagle project tracking. **Scoutbook is the authoritative record; this
pillar syncs with it, it does not replace it.**

**Shipped (per the #92 spec):** the platform-global requirements catalog (`Rank` /
`RequirementSet` — one complete copy per BSA version year / `Requirement` with curated
`stable_key`s and metric conditions / `MeritBadge`), curated 2025 seed data +
`seed-advancement` CLI; tenant-scoped tracking (`MemberRankProgress` with per-rank
version election, `MemberRequirementCompletion`, `MemberMeritBadge`) with the
report → approve workflow and per-tenant `advancement_mode`
(disabled/chair_entry/scout_reported); version-switch remap via `stable_key`; the
**auto-credit engine** (completions recorded automatically from attended events'
activity metrics, badge counts; live progress meters; never re-create, never
auto-revoke) + `recompute-advancement` CLI; the advancement UI (member progress page,
approval queue, settings mode toggle); and the `GroupRule` `rank` dimension ("First
Class and above" dynamic groups).

**Next up (see issues):** Scoutbook CSV import/export (needs real sample files —
the #92 open item); verify the transcribed requirement text against the official PDF.
Deferred: Eagle project workflow, counselor management, purchasing/awarding pipeline,
#123 browser-extension sync.

---

## Pillar 5 — Communications & Reports

**Status: 🚧 Active — messaging core shipped.** · Milestone: *Pillar 5 — Communications & Reports*

UI-heavy and legally sensitive (minors, health data). At ~115 recipients per 40-scout
troop, routine sends are ~1,400 emails/month per troop; at 200 troops that is
~280,000/month. Infrastructure must handle this off the request path and without
vendor lock-in.

**Shipped:** the `NotificationService` abstraction (`EmailBackend` / `SMSBackend` /
`PushBackend` protocols, `app/core/notifications.py`) with the `resend` email backend
(plus an in-memory fake for tests) driving invite-email delivery and event-triggered
emails (creation, cancellation, permission-slip requests); **group-targeted
announcements with a member inbox** (GH-146: compose → audience preview → send/schedule;
send-time audience resolution with per-group parent expansion; web + offline mobile
inbox); the **async email outbox** with per-tenant pacing, exponential-backoff retry,
and a dead-letter surface (GH-78/79 — recipient rows are the queue; in-process loop or
`drain-outbox` cron); **push notifications** (GH-82, Expo tokens, one-shot alert at send
time); `Member` notification-preference fields (`email_opt_out`, `email_bounced`,
`sms_opt_in`) with CAN-SPAM skips decided at resolve time; the consent ledger
(`ConsentRecord` — ToS/COPPA/media/SMS scopes, #223 groundwork). Specs:
[`messaging.md`](docs/spec/messaging.md),
[`group-subscriptions.md`](docs/spec/group-subscriptions.md).

**Next up (see issues):** digest batching ("send now" vs "include in next newsletter",
#218); bounce & complaint webhooks; per-tenant notification config; further email
backends (`smtp` / `ses`); optional SMS backends (`twilio` / `telnyx`); preference
centre. Then the report builder (roster, advancement, swim-classification, PDF export,
medical-form expiry tracking, TWH-compatible export) and the **Natural-Language Reports
(Text-to-SQL)** layer — read-only replica, schema introspection, tenant-guarded
`SELECT` generation via Claude.

---

## Pillar 6 — Web Application Shell & Navigation

**Status: 🚧 Active.** · Milestone: *Pillar 6 — Web App Shell*

The information architecture (three navigation shells; sidebar sub-nav vs. in-page tabs)
is specified in [`navigation.md`](docs/spec/navigation.md).

**Shipped:** collapsible hybrid-IA sidebar; tenant-scoped `GET /auth/session` +
`usePermissions()` / `has()` hook; permission-filtered nav & action buttons;
light/dark theme toggle; Roles & permissions management UI; position-history UI on the
member profile; the platform console shell; shared DataTable with sortable headers and
a central React Query key factory (architecture-review cleanups).

**Next up (see issues):** Home / dashboard landing (announcements, upcoming events, my
action items) to replace the redirect-to-Members default; bulk editing (medical-form dates
and other mass member updates); parent "My Family" permission-scoped views; Resources
(document & link library).

---

## Additional Domains (Future / Undesigned)

**Status: 🧊 Future.** Each needs a `TrackedBase` schema spec before any surface is built.
Filed under the *Future Domains* milestone.

- **Money / Treasury** — per-scout account balances, ledger (dues, fundraiser credits,
  event charges), invoices, budgets. (Was a Phase-1 scope *exclusion*; now a later phase.)
- **Inventory / Equipment** — troop-owned equipment registry and per-member check-out.
- **Content Management / Public Website** — OpenTroop as the troop's public web presence
  (authenticated + anonymous audiences); a lightweight per-troop CMS, edited from Settings,
  not a page builder.

---

## Mobile Applications

**Status: ✅ v1 shipped (iOS, offline-first) — parity & release work active.** · Milestone: *Mobile*

The mobile app is a single **Expo (React Native)** codebase — chosen for maximum code
sharing with the TypeScript web stack (OpenAPI-generated types, a pure-TS sync engine)
while keeping native capabilities first-class via Expo modules (Face ID app lock,
push notifications, keychain). iOS ships first; Android follows from the same code.
The framework decision and phase map (M0–M5) live in issue #93.

**Shipped (the #93 campaign):** the pull-sync protocol
([`sync-protocol.md`](docs/spec/sync-protocol.md), ADR 0002/0005/0006) with eight
keyset-paged `/sync/*` streams; the offline data layer per the #153 spec — a
per-tenant SQLite mirror with page-atomic cursors, mark-and-sweep full refetch, and a
replayable command outbox with a failed-command review screen; v1 screens (roster,
events with RSVP/attendance, offline message inbox + compose, advancement, member
detail, event photos); push notifications (#82); Face ID app lock; personal-calendar
subscription; multi-troop switching with per-identity local-data wipe on sign-out.
Advancement reads stay **online by design** (ADR 0006). Build & release runbook:
[`apps/mobile/docs/build-and-release.md`](apps/mobile/docs/build-and-release.md).

**Open work (see issues):** first-class advancement parity with web (#260); Android
build & release (#212); runtime server selection for self-hosters (#214) and generic
OIDC auth (#215).

---

## What OpenTroop Is Not (Scope Boundaries)

- Not a replacement for Scoutbook as the BSA's authoritative advancement record.
  OpenTroop *syncs* with Scoutbook; it does not compete with it.
- Not a financial management system (dues, fundraiser accounting) in Phase 1.
- Not a national BSA membership registration system.
