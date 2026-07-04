# Using Fable to Advance OpenTroop — Proposal

*Written 2026-07-04. Companion to [`ROADMAP.md`](../ROADMAP.md); issue numbers refer to
[GitHub Issues](../../issues). This is a working proposal, not a spec — the specs for
the work itself live in their tracking issues per repo convention.*

## Progress tracker (live)

> Updated as work lands so the effort can be paused and resumed at any point.
> Decisions in force: **feature branch per phase, PR'd to `develop`, self-merged when
> CI is green**; **Phase 0 is code-only** (Terraform written, `apply` left to Jeff);
> **Phase 5 (Scoutbook CSV) is skipped** until sample export/import files arrive.

| Phase | Scope | Status | Branch / PR |
|---|---|---|---|
| Docs sync + this plan | ROADMAP/README/CLAUDE.md refresh; #175 closed | ✅ merged | PR #180 |
| 0 — Edge security | #116 origin secret + rate limiting + WAF TF; #117 admin auth belt | ✅ merged (`terraform apply` pending — Jeff) | PR #181 |
| 1 — Advancement catalog | Global Rank/RequirementSet/Requirement/MeritBadge models, seed data + CLI, `counts_for_por` / `counts_as_activity`, migration | ✅ merged | PR #183 |
| 2 — Advancement tracking | MemberRankProgress / MemberRequirementCompletion / MemberMeritBadge, workflow, `advancement_mode`, API | ✅ merged | PR #184 |
| 3 — Auto-credit engine | metrics + thresholds + triggers + `recompute-advancement` CLI | ✅ merged | PR #185 |
| 4 — Advancement UI | Member progress page, approval queue, settings mode toggle, sidebar | ✅ merged | PR #187 |
| 5 — Scoutbook CSV | import/export | 🚫 blocked — needs sample files from Jeff | — |
| 6 — GroupRule `rank` dimension | dynamic groups by current rank | ✅ merged | PR #186 |
| Advancement viewer UI | #191 scout picker + sub-page IA | ✅ merged | PR #192 |
| **Mobile v1 — M0** docs alignment | Expo decision (iOS first) recorded in ROADMAP/README | ✅ merged | this PR |
| **Mobile v1 — M1** server sync surface | `Syncable` + `/sync/*` for event_types, locations, events, participants, relationships | ✅ merged | PR #194 |
| **Mobile v1 — M2** shared types | `packages/api-types` from the gen-api pipeline + CI drift | ✅ merged | PR #195 |
| **Mobile v1 — M3** Expo scaffold | #93: apps/mobile shell, Clerk, troop switcher, CI | ✅ merged | this PR |
| **Mobile v1 — M4** offline data layer | #153 design: mirror + pull loop + command queue, Node-tested | ✅ merged | PR #197 |
| **Mobile v1 — M5** v1 screens | roster/events/attendance/RSVP on the mirror; Face ID app lock | ✅ merged | PR #198 |
| Family-scoped sync | offline RSVP for members without member:read (self + wards + co-parents mirror) | ✅ merged | PR #199 |
| Push notifications (#82) | Expo Push Service backend + PushToken registration + mobile opt-in toggle | ✅ merged | PR #200 |
| Mobile advancement tab | scout picker, rank view, completion entry with dates (online surface) | ✅ merged | PR #201 |

**Resume-here notes:** *(keep this current — most recent first)*
- 2026-07-04 (final): **entire train merged** — #180, #181, #183, #184, #185, #186,
  #187 all landed on `develop`; #116/#117/#175 closed. Backend suite: 503 tests.
  Every planned phase is done except Phase 5 (Scoutbook CSV, blocked on sample
  files). Jeff's open follow-ups: `terraform apply` (edge security), verify
  ranks-2025.json vs the official PDF, Scoutbook sample files, and
  `uv run seed-advancement` on deploy. **Next campaign per the plan: Mobile v1**
  (formalize #153 into a spec, extend `Syncable` to events/participants/groups,
  Expo scaffold #93) — see "Phase 6 — Mobile v1" below.
- 2026-07-04 (later still): **all planned phases are code-complete.** Branch stack:
  phase2 → phase3 → phase6 → phase4, each already merged forward; PR train is
  sequential (merge #184 → PR phase3 → PR phase6 → PR phase4 — each branch diff
  against develop shrinks to its own phase once its parent merges). This file's
  final state + ROADMAP/CLAUDE.md Pillar-4 updates ride the phase4 PR.
  **Jeff's follow-ups:** (1) `terraform apply` for edge security (#181, see
  terraform/README.md); (2) verify `backend/data/advancement/ranks-2025.json`
  against the official BSA PDF (transcribed from model knowledge — see the file's
  README; corrections = edit + `uv run seed-advancement`); (3) Scoutbook sample
  export/import files to unblock Phase 5; (4) run `uv run seed-advancement` as a
  deploy step / after migrating. Remaining #92 scope: Phase 5 only. #169 can be
  closed when Phase 5 lands or re-scoped to it.
- 2026-07-04 (later): #181 merged (edge security — **Jeff still owes the
  `terraform apply`**, see terraform/README.md "Edge security rollout"). Phase 1
  (catalog + seed data + `seed-advancement` CLI) is PR #183. Phase 2 (tracking
  models + workflow API + `advancement_mode`) is fully implemented and tested on
  `claude/phase2-advancement-tracking`, stacked on Phase 1 — PR it to `develop`
  once #183 merges. ⚠️ ranks-2025.json was transcribed from model knowledge
  (PDF unfetchable here) — verify against the official PDF; corrections are a
  data edit + `uv run seed-advancement`. Next actions: merge #183 when green →
  PR phase2 → Phase 3 (auto-credit engine) on a branch off phase2.
- 2026-07-04: Phase 0 implemented and PR'd (#181): origin-auth + rate-limit middleware,
  CF Access belt on /platform, tenant-header flag, Terraform (WAF/rate-limit rules and
  Access app, all opt-in) + Worker header injection. **Jeff's follow-ups:**
  `terraform plan/apply` per terraform/README.md "Edge security rollout"; enable the
  opt-in vars when the Cloudflare plan allows. Next action: merge #181 when CI is
  green; start Advancement Phase 1 off `develop`.
- 2026-07-04: Plan approved by Jeff (feature-branch + self-merge; Phase 0 code-only).
  Task list mirrors the phases. Next action: Phase 0 branch off `develop`.

## Where the project stands

Pillars 1 (Roster/RBAC) and 2 (Multi-tenant isolation) are shipped and hardened —
the July 2026 security audit (#175, now closed) confirmed the auth/tenancy design and
its two substantive code findings are fixed. Pillar 3 (Events) is functionally rich:
RSVP, permission slips, audiences, iCal feeds, calendar UI, and event-triggered email
all work. Pillar 5 has real notification plumbing (vendor-agnostic service, Resend
backend) but no async queue. Critically, **two large design efforts are already done
and sitting in issues waiting for implementation**:

- **Advancement (#92)** — a complete, decisions-locked data-model spec: versioned
  global requirements catalog, per-scout/per-rank version election, report → approve
  workflow, auto-credit from event attendance, Scoutbook CSV import/export.
- **Mobile offline data layer (#153)** — a full design narrative: local mirror per
  tenant + replayable-action outbox, riding the shipped sync protocol
  (`sync-protocol.md`, `GET /sync/members`).

That changes the question from "what should we design next?" to "which finished design
do we build first, and how do we spend frontier-model capacity doing it?"

## The candidates

| Option | Readiness | Why it's attractive | Why not first |
|---|---|---|---|
| **Advancement (#92 → #169)** | Spec locked; only the Scoutbook file mapping awaits sample files | Most complex domain in the product; the differentiating feature vs. TWH (auto-credit from attendance); unlocks the `rank` group dimension and the report builder | Biggest single effort |
| **Mobile v1 (#153 → #93)** | Design narrative exists; needs formal spec + sync coverage for events | Offline-first is the project's core promise; attendance-at-camp is the killer use case | Building a client against a still-moving API contract (advancement will add major surface); #153 itself says the spec must be formalized first |
| **Comms infra (#78–#82)** | Specs partial | Roadmap calls it the gating unblock for messaging features | Mostly well-understood infrastructure (queue, retries, webhooks) — doesn't need a frontier model |
| **Edge security (#116, #117)** | Fully specced in the issues | The only `high priority` open issues; #175's Finding 3 was deferred here | Small and bounded — a prerequisite chore, not a campaign |

## Recommendation

**Make Advancement the flagship Fable project, with the edge-security pair landed
first as a short opening act, and mobile as the immediate follow-on.** Reasoning:

1. **Fable's leverage is proportional to domain complexity.** Advancement is the one
   pillar the roadmap calls "the most complex domain": a two-level requirement
   hierarchy with container semantics, BSA version elections with renumbering-safe
   remapping (`stable_key`), an auto-credit engine with never-auto-revoke semantics,
   and a three-way trust boundary with Scoutbook as the authoritative record. This is
   exactly the work where a frontier model outperforms — subtle invariants, many
   interacting rules, high cost of a wrong schema. Queue infrastructure and CRUD UI
   are not.
2. **It's unblocked today.** The #92 spec is locked; 5 of its 6 implementation phases
   need no external input. Mobile, by its own tracking issue, still needs the
   REST-vs-GraphQL decision and a formalized offline spec, and every API surface
   advancement adds is churn a premature mobile client would have to absorb.
3. **It compounds.** Advancement lights up the dormant `GroupRule` `rank` dimension
   ("First Class and above" dynamic groups), feeds the report builder (#147), and
   gives mobile something worth syncing beyond the roster.
4. **Security first is cheap insurance.** #116/#117 are High priority, already
   specced, and mostly Terraform/middleware. Landing them first means every
   subsequent feature ships onto a locked origin instead of retrofitting later.

Mobile is the right *second* act, not a wrong answer — sequencing it after
advancement Phase 1–3 means the sync contract it freezes against includes the
advancement tables, and the at-camp story ("take attendance offline, advancement
credits post automatically when you're back in signal") becomes the launch demo.

## Sequenced plan

### Phase 0 — Lock the front door (~small)
- **#116**: origin shared-secret/mTLS so `TRUST_FORWARDED_HOST` is sound; Cloudflare
  WAF + rate-limit rules; per-tenant app-layer rate limiting; disable `X-Tenant-ID`
  fallback in prod. **#117**: edge auth belt for `admin.*`.
- Fable role: the middleware/Terraform design and the tests-first security assertions.

### Phase 1–3 — Advancement backend (#169, per the #92 spec's own ordering)
1. Catalog models + seed pipeline + 2025/2026 requirement transcription
   (+ `Position.counts_for_por`, `EventType.counts_as_activity`, migrations, RLS).
2. Tracking models + CRUD + report→approve workflow + `advancement_mode` setting.
3. Auto-credit engine (`app/core/advancement.py`) + recompute triggers + CLI.
- Fable role: schema/migrations, the auto-credit and version-election/remap logic,
  and the permission wiring — the places where a subtle bug corrupts a scout's record.

### Phase 4 — Advancement UI
- Member advancement tab (per-rank checklists, metric progress meters), approval
  queue, settings toggle. Adopt **#167 (react-hook-form + zod)** here — the spec
  explicitly names these forms as the trigger for that migration.

### Phase 5 — Scoutbook CSV import/export
- ⚠️ **Blocked on you:** a real Scoutbook advancement export and a sample of the
  Internet Advancement *import* format (see "What we need from Jeff" below). Nothing
  else waits on this — it's deliberately last.

### Phase 6 — Mobile v1 (underway)
- #153 spec is written and accepted (REST via OpenAPI, per-tenant SQLite mirror,
  replayable command queue). Framework confirmed as **Expo (React Native), iOS
  first** — decision matrix and M0–M5 phase map in #93. Offline reads of
  everything + offline writes for attendance/RSVP only; Face ID app lock;
  push (#82) after v1. Jeff-side steps when due: Apple Developer account,
  EAS project + TestFlight, APNs keys.

Comms infra (#78 queue, #79 retry/DLQ, #80 webhooks) can proceed **in parallel at any
point** — see the delegation section, since it's the clearest candidate for
lower-tier models working from tight specs.

## Sub-agent / model-tier delegation

The principle: **Fable designs, decides, and reviews; lower tiers execute against
patterns that already exist in the repo.** OpenTroop is unusually delegation-friendly
because its conventions are strong (TrackedBase contract, `require()` guards, seeded
RBAC, spec-in-issue) and its CI is a real safety net (pytest, mypy, ruff, tsc,
eslint, generated-types drift check, Playwright smoke, CodeQL).

| Work | Tier | Rationale |
|---|---|---|
| Schema design, migrations, RLS policies, auto-credit engine, version-election remap, security middleware (#116/#117), Scoutbook collision rules | **Fable** | Wrong-answer cost is data corruption or privilege escalation; invariants span many files |
| Spec-to-issue breakdown, PR review of all delegated work | **Fable** | Review is where the frontier tier pays for itself on delegated code |
| Rank-requirement JSON transcription from the official BSA PDF (`ranks-2025.json`, `ranks-2026.json`, `merit-badges.json`) | **Sonnet**, Fable spot-check | Mechanical transcription against a fixed schema; verifiable against the PDF; ~hour-scale |
| CRUD routers + Pydantic schemas + tests that mirror existing patterns (e.g. merit-badge endpoints copying the completion endpoints) | **Sonnet** | The repo has a dozen worked examples; tests-first convention constrains drift |
| Frontend forms/pages following existing pages (advancement tab scaffolding, approval queue table on the shared DataTable) | **Sonnet** | Component patterns, query-key factory, and DataTable already exist to copy |
| #167 react-hook-form/zod migration of existing forms | **Sonnet/Haiku** | Rote, well-documented library migration; tsc + tests catch regressions |
| Comms infra #79/#80 (retry/DLQ, bounce webhooks) once Fable specs the queue (#78) | **Sonnet** | Standard infrastructure with abundant prior art |
| Codebase reconnaissance during any of the above | **Explore agents (Haiku)** | Cheap fan-out search; conclusions only |
| Quick wins between phases: #83 multi-day event bars, #141 dashboard landing, #142 bulk edit | **Sonnet**, Fable review | UI work with existing primitives; good background-session fodder |

Practical loop per work item: Fable writes/refines the spec in the tracking issue →
delegates bounded implementation to a Sonnet session/sub-agent with the issue as the
brief → Fable reviews the diff (using the `code-review` / `security-review` skills on
anything touching auth, tenancy, or minors' data) → CI green → merge to `develop`.
Keep sub-agent tasks issue-sized, not pillar-sized — the failure mode to avoid is a
lower-tier session making schema decisions because the brief left room for them.

## What we need from Jeff

1. **Scoutbook sample files** (unblocks Phase 5 only): a real advancement export CSV
   from your troop's Scoutbook/Internet Advancement, and if possible a sample of the
   file format Internet Advancement *accepts* for import. Anonymized is fine — the
   TWH `anonymize-twh` pattern can be repeated.
2. **Cloudflare/GCP access or values for #116/#117** when Phase 0 starts (Terraform
   applies the rules, but enabling WAF managed rulesets and the origin secret touches
   the live zone).
3. **A green light on the sequencing above** — or a re-order; the phases are
   independent enough that "mobile before advancement UI" is viable if the summer-camp
   window matters more to you than API stability.
