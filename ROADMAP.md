# OpenTroop Roadmap

OpenTroop is a community-driven, offline-first replacement for TroopWebHost.
This document describes the four capability pillars and how they build on each other.
Granular tasks are tracked via GitHub Issues and Milestones.

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
- [ ] Initial Alembic migration (requires live Postgres)
- [ ] FastAPI CRUD endpoints for Patrol, Member, MemberRelationship
- [ ] Role-based access control (Scoutmaster, ASM, Committee Chair, read-only parent)
- [ ] Auth (JWT; consider Scoutbook SSO as a future option)
- [ ] TroopWebHost roster CSV import
- [ ] Scoutbook member export import (BSA recharter format)
- [ ] Multi-tenant provisioning (troop onboarding flow)

### Pillar 2 — Events & Calendar

Event types differ meaningfully. Campouts carry permit numbers and capacity limits.
Merit badge clinics have prerequisites. Courts of Honor tie into advancement data.
Model events generically with typed metadata rather than one-size-fits-all fields.

- [ ] Analyze TroopWebHost event export format before designing the model
- [ ] Core `Event` model (name, type, dates, location, capacity, tenant-scoped)
- [ ] Event types: meeting, campout, service project, merit badge clinic, court of honor, fundraiser
- [ ] RSVP / attendance tracking per member
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

- [ ] Report builder: roster by patrol, advancement summary, swim classification list
- [ ] PDF export for reports and permission slips
- [ ] Parent/guardian contact directory (scoped by guardian links)
- [ ] Bulk email / announcement to troop or patrol
- [ ] Medical form storage with expiration tracking (BSA Annual Health & Medical Record)
- [ ] TroopWebHost-compatible data export (migration path for troops leaving TWH)

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

1. **Export and analyze** TroopWebHost + Scoutbook data from a real troop before
   building Event or Advancement models.
2. **Initial Alembic migration** — `docker compose up db` then
   `alembic revision --autogenerate -m "initial schema"`.
3. **CRUD API endpoints** for Pillar 1 models with auth.
4. **License, contributing guide, and GitHub project structure** for public launch.

---

## What OpenTroop Is Not (Scope Boundaries)

- Not a replacement for Scoutbook as the BSA's authoritative advancement record.
  OpenTroop syncs with Scoutbook; it does not compete with it.
- Not a financial management system (dues, fundraiser accounting) in Phase 1.
- Not a national BSA membership registration system.
