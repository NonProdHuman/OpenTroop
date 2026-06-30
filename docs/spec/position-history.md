# Position History Spec

**Status:** Implemented (backend + importer; full show/edit history UI is a follow-up)
**Pillar:** Roster & Relationships (Pillar 1) — RBAC extension
**Related:** [`roles-rbac.md`](roles-rbac.md) · [`members-screen.md`](members-screen.md) · [`session-permissions.md`](session-permissions.md)
**Resolves:** roles-rbac open question #2 ("Position term/history") and #4 ("TWH importer mapping")

---

## Overview

Today a member's position assignment (`MemberPositionAssignment`) records only *that* a
member holds a position — `created_at` plus a soft-delete tombstone. There is no notion of
**when a term started or ended**. A position is "held" until the assignment row is
soft-deleted, at which point it vanishes from history entirely.

This is insufficient for two real needs that surfaced during the TroopWebHost (TWH) import:

1. **TWH exports carry full term history.** Every leadership term a scout or adult has ever
   held lives in `Scout_Leadership_History` / `Adult_Leadership_History`, each row stamped
   with a `Start_Date` and (for ended terms) an `End_Date`. A typical scout has 5–10 rows.
   Throwing away everything but the current term loses data troops care about (leadership
   tenure drives rank advancement requirements, courts of honor, and "years of service"
   recognition).

2. **Leaders need to see and edit tenure.** "When was Alice Patrol Leader?" and "correct
   Bob's Scoutmaster start date" are routine roster operations. The current model can't
   answer either.

This spec adds **term dating** to position assignments so the importer can load full
history, the permission resolver counts only *current* terms, and the UI can show and edit
both current and past positions.

> **Scope boundary.** This spec covers the data model, the permission-resolver change, the
> API, the importer mapping, and the UI contract. It does **not** change the two-level RBAC
> shape (`member → Position → FunctionalRole → Permission`) — only how an *assignment* is
> dated. Positions and functional roles are untouched.

---

## The core change: assignments become dated terms

A `MemberPositionAssignment` becomes a **term**: a member held a position from a start date
to an (optional) end date. Two nullable, timezone-aware columns are added:

| Column | Type | Meaning |
|---|---|---|
| `start_date` | `date` (nullable) | When the term began. Nullable because legacy/manual assignments may not know it; a null start is treated as "has always held it" for currency checks. |
| `end_date` | `date` (nullable) | When the term ended. **Null ⇒ current.** A non-null end date in the past ⇒ historical. |

### Currency rule (single source of truth)

An assignment is **current** iff:

```
is_deleted = false  AND  (end_date IS NULL OR end_date >= today)
```

- `is_deleted` stays as the hard tombstone — "this row was created in error, ignore it
  entirely." It is **distinct** from `end_date` — "this term legitimately ended." A
  soft-deleted row never counts, current or historical; an ended row counts as *history*
  but not as *current*.
- `end_date >= today` (rather than `IS NULL` only) lets a leader schedule a known
  turnover date in advance without the position silently dropping early. A future end date
  is still current until the day arrives.
- `start_date` is **not** gated for currency (a null or future start still counts as
  current if not ended). Rationale: troops routinely record "elected, term starts next
  month" and expect the position to show now. We can revisit if this proves surprising.

This rule lives in **one** place — a helper in `app/core/permissions.py` (e.g.
`current_assignment_clause()` returning a SQLAlchemy boolean) — and every reader
(resolver, members screen, group position rules) uses it. No reader re-implements the
predicate inline.

---

## Why the resolver must change (the alumni-permissions bug)

`resolve_permissions(member_id, session)` currently walks **every** non-soft-deleted
`MemberPositionAssignment`. If the importer loaded ended terms as plain assignments, a
scout who was Senior Patrol Leader in 2019 would **still resolve SPL permissions today** —
and an adult who termed out of Committee Chair would keep its admin-ish grants forever.

So the resolver change is **load-bearing, not cosmetic**: the moment we store history, the
resolver MUST filter to *current* terms via the currency rule above. This is the reason
history can't be bolted on without touching permissions.

`app/core/groups.py` (`resolve_group_members` / `member_group_ids`, which back
`GroupPositionRule`) has the **same** exposure — a dynamic "PLC = everyone holding PL/SPL"
group would otherwise include every scout who ever held the position. Both resolvers adopt
the shared currency clause in the same change.

### Resolver test matrix (must all hold)

| Scenario | `resolve_permissions` includes the position's perms? |
|---|---|
| `end_date` null | ✅ yes (current) |
| `end_date` in the future | ✅ yes (current) |
| `end_date` in the past | ❌ no (historical) |
| `is_deleted` true (any dates) | ❌ no (tombstoned) |
| `start_date` in the future, `end_date` null | ✅ yes (see currency rule note) |
| Member holds the same position twice — one ended, one current | ✅ yes (the current term carries it) |

---

## Data model

### Option A (chosen): date the existing assignment row

Add `start_date` / `end_date` to `MemberPositionAssignment`. One row = one term. A member
who held Patrol Leader twice has two rows (one ended, one current). The existing
`uq_member_position_assignments (member_id, position_id)` unique constraint is **dropped** —
it's incompatible with repeat terms — and replaced with nothing at the DB level; duplicate
*active* terms are prevented in the API layer (see [Invariants](#invariants)).

**Pros:** smallest change; no new table; existing FKs (`assigned_by_id`), RLS policy, and
`member_assignments` relationship are reused as-is. **Cons:** the assignment table now
mixes "current" and "historical" rows; every reader must apply the currency clause.

### Option B (rejected): separate `position_term` history table

Keep `MemberPositionAssignment` as current-only; add a parallel `PositionTerm` history
table. **Rejected** because it duplicates the member↔position relationship in two tables
that must be kept in sync (every assign/unassign writes both), and the resolver would still
need to join history to answer "current." Option A with a currency clause is simpler and
has one source of truth.

**Decision: Option A.** Removing the unique constraint is the only schema subtraction; the
two added columns are additive.

### Migration

A single Alembic migration:

```python
def upgrade() -> None:
    op.add_column("member_position_assignments",
        sa.Column("start_date", sa.Date(), nullable=True))
    op.add_column("member_position_assignments",
        sa.Column("end_date", sa.Date(), nullable=True))
    op.drop_constraint("uq_member_position_assignments",
        "member_position_assignments", type_="unique")
    # RLS already enabled on this table (it predates this change) — no rls.* call needed.

def downgrade() -> None:
    op.create_unique_constraint("uq_member_position_assignments",
        "member_position_assignments", ["member_id", "position_id"])
    op.drop_column("member_position_assignments", "end_date")
    op.drop_column("member_position_assignments", "start_date")
```

No backfill is required: existing rows get `start_date = end_date = NULL`, which the
currency rule reads as "current, start unknown" — preserving today's behavior exactly for
data created before this change. (`member_position_assignments` already has its RLS policy
from the initial RBAC migration; adding columns doesn't require re-running `rls.*`. The
policy-completeness test is unaffected because no table is added.)

### Invariants (API-enforced, not DB-enforced)

The dropped unique constraint moves duplicate-prevention into the service layer:

- **At most one *current* term per (member, position).** Assigning a position a member
  already currently holds is a 409, not a second row. (Ended terms don't count — you can
  re-assign a position someone previously held.)
- **`end_date >= start_date`** when both are set — 422 otherwise.
- Ending a term sets `end_date`; it does **not** soft-delete. Soft-delete remains reserved
  for "created in error."

---

## API

All routes are tenant-scoped and gated by the existing `role:assign` permission
(`Permission.ROLE_ASSIGN`), consistent with how positions are assigned today.

| Method & path | Purpose | Notes |
|---|---|---|
| `GET /members/{id}/positions` | List a member's terms | `?current=true` (default) filters via the currency clause; `?current=false` returns full history, newest-first by `start_date`. |
| `POST /members/{id}/positions` | Assign a position (start a term) | Body: `position_id`, optional `start_date` (default: today), optional `end_date`. 409 if a current term for that position exists. |
| `PATCH /members/{id}/positions/{assignment_id}` | Edit a term's dates | Correct `start_date` / set `end_date` (ending a term) / reopen (clear `end_date`). Enforces `end_date >= start_date`. |
| `DELETE /members/{id}/positions/{assignment_id}` | Soft-delete a term | "Created in error." Distinct from ending — removes from history. |

Schemas (`app/schemas/rbac.py`): extend the assignment read schema with `start_date`,
`end_date`, and a derived `is_current: bool` (computed from the currency rule so the
frontend never re-derives it). Add `*Create` / `*Update` carrying the date fields.

> The existing members screen reads a member's "primary role/position"; that selector now
> means "a current term," and uses the currency clause. No member-list query should surface
> a historical position as if it were live.

---

## TWH importer mapping (resolves roles-rbac open question #4)

### Source tables

- **Catalog:** `Leadership_Position` (and the legacy parallel `BSA_Leadership_Position`) —
  `i` (id) → `Position` (name), `Position_Code`, `Adult_Flag`, `Display_Sequence`. Both
  tables share ids; read both and merge (identical ids carry identical names).
- **History:** `Adult_Leadership_History` and `Scout_Leadership_History` — each row has
  `Person_ID`, `BSA_Leadership_Position_ID` (→ catalog `i`), `Start_Date`, and `End_Date`
  (empty for current terms).

### Mapping rules

1. **Positions are created only when actually used** — i.e. referenced by at least one
   history row whose `Person_ID` resolves to an imported member. Unused catalog entries are
   ignored (a troop's catalog lists dozens of positions it has never filled).
2. **Match seeded positions deterministically — three tiers, no fuzzy matching.** For each
   used catalog entry, resolve to an OpenTroop `Position` in this order:
   1. **Exact slug match.** Slugify the TWH `Position` name (`"Assistant Scoutmaster"` →
      `assistant-scoutmaster`) and match an existing `Position.slug` in the tenant. Handles
      the bulk that already line up (`Scoutmaster`, `Patrol Leader`, `Committee Member`, …).
   2. **BSA `Position_Code` crosswalk.** A small static dict maps the canonical BSA code to a
      seeded slug for cases where names differ but the code is unambiguous. Confirmed from
      real exports: `SM`→`scoutmaster`, `SA`→`assistant-scoutmaster`, `CC`→`committee-chair`,
      `CR`→`chartered-org-rep`, `MC`→`committee-member`. Extended as more codes are observed
      (scout codes `SPL`, `PL`, … added when seen). Codes are a controlled, unique vocabulary,
      so there is no collision risk.
   3. **Create a new non-system `Position`.** Anything still unmatched (custom troop roles,
      scout positions with no code that don't name-match) is created fresh
      (`is_system=False`, `applies_to` from `Adult_Flag`, `sort_order` from
      `Display_Sequence`). It imports as a plain title with **no permissions** — safe by
      default; the troop can map it into a functional role later.

   **Fuzzy/similarity matching is explicitly rejected.** In an RBAC context the near-miss
   names are precisely the ones with *different* permissions — `Committee Chair` vs
   `Committee Member`, `Scoutmaster` vs `Assistant Scoutmaster`, `Patrol Leader` vs `Senior
   Patrol Leader`. A wrong match silently mis-grants authority, so the high false-positive
   cost rules out similarity scoring; tier 2's exact code table is the deliberate alternative.

   **Every created (tier-3) position is surfaced** in the import result (`warnings` plus the
   `positions` count) so the admin sees "created N new positions: […] — review and assign
   functional roles if needed" rather than silent drift.
3. **Import full history, dated.** For every history row (current *and* ended), write one
   `MemberPositionAssignment` with `start_date` ← `Start_Date` and `end_date` ← `End_Date`
   (null for current). This is the change from the current-only prototype: ended terms are
   now persisted, not skipped, because the schema can hold them and the resolver ignores
   them for permissions.
4. **Dedup** on `(member_id, position_id, start_date)` to guard against duplicate XML rows.
5. **Warn + skip** a history row whose position id isn't in the catalog or whose person
   wasn't imported (counts toward `result.skipped` / `result.warnings`, matching the
   existing importer convention).

### Importer result additions

`TwhImportResult` gains `positions` (created) and `position_assignments` (terms written);
`TwhImportRead`, the `/import/twh` response, and the `import-twh` CLI summary surface both.

### Importer test additions (fixture: `sample_twh_minimal.xml`)

- Catalog entries for an adult position matching a seeded slug (`Scoutmaster`), an adult
  position that doesn't (`Committee Chairman`), and a scout position matching a seeded slug
  (`Patrol Leader`).
- History rows: a current adult term, a current scout term, an **ended** term (asserts it's
  stored with `end_date` set and is **excluded** from `resolve_permissions`), and a row with
  an unknown position id (asserts warn + skip).
- A test seeding default RBAC first, then importing, asserting the seeded `Scoutmaster`
  position is **reused** (same id, `is_system=True`) rather than duplicated.

---

## UI contract (frontend — separate task)

The frontend work is **out of scope for the backend change** but the contract is fixed here
so the API is built to fit it. On the member detail/edit screen (`members-screen.md`):

- **Current positions** render as the primary list (chips/badges), unchanged from today's
  visual except sourced from `?current=true`.
- A **"Position history"** disclosure lists ended terms with start/end dates, newest-first,
  visible to `role:assign` holders (and to the member for their own record).
- **Assign** opens a position picker (filtered by `applies_to` vs the member's type) with an
  optional start date (default today).
- **End a term** sets `end_date` (date picker, defaults today); **edit** corrects either
  date; **delete** ("created in error") is a separate, confirm-gated action distinct from
  ending.
- The `is_current` flag from the read schema drives which section a term renders in — the
  frontend never re-derives currency from dates.

---

## Decisions

- **Date precision is `date`, not `datetime`.** TWH stores midnight-stamped dates; troop
  tenure is a calendar concept ("started July 2024"). Matches `MemberPositionAssignment`'s
  sibling date fields and avoids timezone ambiguity on a term boundary.
- **Future `end_date` is still current.** Supports scheduled turnover; the currency clause
  uses `end_date >= today`, not `IS NULL` only.
- **One row per term (Option A), unique constraint dropped**, duplicate-active-term
  prevention moved to the API. One source of truth for currency.
- **Importer loads full history** once the schema can hold it (this spec), reversing the
  current-only prototype's skip-ended behavior.
- **Importer matching is deterministic** (exact slug → BSA code crosswalk → create new); no
  fuzzy/similarity matching, because near-miss position names carry different permissions.
- **Singletons are not enforced.** A position may have multiple current holders;
  "one Scoutmaster / one SPL" is advisory only (resolves roles-rbac open question #1).
- **Future-dated terms are current.** A future `start_date` counts as current (not just a
  future `end_date`) — supports recording elections ahead of the term start. No
  `start_date <= today` gate.

## Open questions

1. **`assigned_by_id` on import.** Imported terms have no OpenTroop actor to credit.
   Proposed: leave null (the audit trail legitimately starts at import); consider a synthetic
   "imported from TWH" marker later.
