# Using Fable to Advance OpenTroop — Proposal

*Written 2026-07-04. Companion to [`ROADMAP.md`](../ROADMAP.md); issue numbers refer to
[GitHub Issues](../../issues). This is a working proposal, not a spec — the specs for
the work itself live in their tracking issues per repo convention.*

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

### Phase 6 — Mobile v1
- Formalize #153 into a spec (REST decision, outbox action registry, per-tenant
  SQLite layout); extend `Syncable` to events/participants/groups (the "four
  read-only endpoints" #153 estimates); Expo scaffold (#93); offline reads of
  everything + offline writes for attendance/RSVP only.

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
