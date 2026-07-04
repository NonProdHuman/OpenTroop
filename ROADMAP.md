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
requests, riding the Pillar 5 notification service.
Specs: [`event-edit.md`](docs/spec/event-edit.md),
[`event-rsvp-permission.md`](docs/spec/event-rsvp-permission.md),
[`member-event-create.md`](docs/spec/member-event-create.md).

**Next up (see issues):** health-form collection & storage; permission-slip PDF
export; multi-day event bars in the month view. Deferred: universal sign-up slots
(the redesign superseding TWH's event-shift model).

---

## Pillar 4 — Advancement & Requirements

**Status: 🔜 Next up — spec drafted, ready to implement.** · Milestone: *Pillar 4 — Advancement*

The most complex domain. BSA advancement has a strict hierarchy
(program → rank → requirements → sub-requirements), merit badges with counselor
sign-offs, and Eagle project tracking. **Scoutbook is the authoritative record; this
pillar syncs with it, it does not replace it.**

**Designed:** the full data-model spec lives in issue #92 (versioned, platform-global
requirements catalog; per-scout, per-rank version election; report → approve workflow;
automatic crediting of countable requirements from event attendance; Scoutbook CSV
import/export). Implementation is tracked in #169.

**Next up (see issues):** implement per the #92 spec — catalog models + seed pipeline,
tracking models + workflow, auto-credit engine, advancement UI, Scoutbook CSV
import/export (the one step still awaiting real sample files), and lighting up the
`GroupRule` `rank` dimension. Deferred: Eagle project workflow, counselor management,
purchasing/awarding pipeline, #123 browser-extension sync.

---

## Pillar 5 — Communications & Reports

**Status: 🔜 Next up (highest-leverage unblock).** · Milestone: *Pillar 5 — Communications & Reports*

UI-heavy and legally sensitive (minors, health data). The **notification infrastructure**
is the gating prerequisite — it unblocks invite emails (Pillar 1), event notifications
(Pillar 3), and all messaging below.

At ~115 recipients per 40-scout troop, routine sends are ~1,400 emails/month per troop;
at 200 troops that is ~280,000/month. Infrastructure must handle this off the request
path and without vendor lock-in.

**Shipped groundwork:** the `NotificationService` abstraction (`EmailBackend` /
`SMSBackend` protocols, `app/core/notifications.py`) with the `resend` email
backend (plus an in-memory fake for tests) driving invite-email delivery today;
event-triggered emails (creation, cancellation, permission-slip requests) resolving
recipients through the same audience/group primitives as event visibility; `Member`
notification-preference fields (`email_opt_out`, `email_bounced`, `sms_opt_in`); and
the tenant-scoped settings surface (currently permission-slip language). Specs already
drafted: [`messaging.md`](docs/spec/messaging.md),
[`group-subscriptions.md`](docs/spec/group-subscriptions.md).

**Next up (see issues):** further email backends (`smtp` / `ses`); optional SMS
backends (`twilio` / `telnyx`); async send queue
with per-tenant rate limiting; retry / dead-letter; bounce & complaint webhooks; a
`TroopSettings`-style per-tenant notification config; push via FCM. Then the messaging
features (group-targeted announcements, event-triggered
notifications, digests, SMS opt-in, preference centre), the report builder (roster,
advancement, swim-classification, PDF export, medical-form expiry tracking,
TWH-compatible export), and the **Natural-Language Reports (Text-to-SQL)** layer
— read-only replica, schema introspection, tenant-guarded `SELECT` generation via Claude.

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
(document & link library); event-linked photo gallery.

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

**Status: 🧊 Future — groundwork started; apps after the API contract stabilizes.** · Milestone: *Mobile*

Native iOS (Swift/SwiftUI) and Android (Kotlin/Compose) apps are the offline-sync clients
for Pillars 1–4 — developed in parallel once each pillar's API contract stabilizes, not as
a separate phase.

**Shipped groundwork:** the pull-sync protocol spec
([`sync-protocol.md`](docs/spec/sync-protocol.md)) with the `Syncable` mixin
(`sync_seq` cursor) and the first keyset-paged pull endpoint (`GET /sync/members`);
the offline data-layer design (full local mirror per tenant + replayable-action
outbox) is drafted in issue #153.

**Open work (see issues):** REST-vs-GraphQL API review; formalize the #153 offline
data-layer spec; extend `Syncable` to events/groups; the client apps (Expo scaffold
#93 is the tracked starting point); push-notification integration.

---

## What OpenTroop Is Not (Scope Boundaries)

- Not a replacement for Scoutbook as the BSA's authoritative advancement record.
  OpenTroop *syncs* with Scoutbook; it does not compete with it.
- Not a financial management system (dues, fundraiser accounting) in Phase 1.
- Not a national BSA membership registration system.
