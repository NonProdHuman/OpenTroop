# Dynamic Groups Refinement Spec

**Status:** Draft
**Routes:** `/groups/{id}/rules` (API) · `/groups/{id}/edit` · `/groups/new` (rule editor UI)
**Pillar:** Roster & Relationships (Pillar 1) — Groups & Audiences
**Related:** [`dynamic-group-rules.md`](dynamic-group-rules.md) · [`groups-screen.md`](groups-screen.md) · [`group-subscriptions.md`](group-subscriptions.md)
**Builds on:** [`dynamic-group-rules.md`](dynamic-group-rules.md) (the now-shipped general rule engine)

---

## Overview

The general-purpose rule engine from [`dynamic-group-rules.md`](dynamic-group-rules.md)
is live: `GroupRule` rows per dimension, a per-group `rule_logic` AND/OR toggle, and a
checkbox-row editor on the group edit page. Real use has surfaced four refinements:

1. **"Parents/Guardians of group" is the wrong shape as a rule.** It currently lives in
   the AND/OR rule pool, where it produces nonsense (intersecting "parents" with "scouts"
   empties the group). It becomes a **post-resolution expansion toggle** — resolve the
   group normally, then optionally add the parents/guardians of whoever resolved.
2. **The rule editor UI feels dated.** Move to a modern "filter → bubble" builder with
   type-ahead, keep-open multi-select pickers, and removable chips.
3. **Per-filter AND/OR mixing — deferred.** Once #1 removes the relationship wart, the
   single top-level AND/OR is expected to suffice. Revisit with a Mailchimp-style
   "OR of AND-groups" model only if a concrete unmet need appears (see
   [Deferred](#deferred-per-filter-andor)).
4. **Collapse `manual` + `dynamic` group types into one `custom` type.** The resolver
   already unions manual members with rules regardless of type; the manual/dynamic split
   is a UI gate only. A `custom` group supports **both** manual adds and dynamic rules.
   `patrol` stays distinct (one-per-member, adults excluded).

Items #1, #2, and #4 ship together; they reinforce each other (a `custom` group's
"include parents" toggle naturally applies to its full manual + dynamic membership).

---

## 1. Parents/Guardians as a post-resolution expansion

### Problem

`relationship` is today a `RuleDimension`: it takes target group IDs and contributes
"parents of those groups' members" into the same AND/OR pool as every other rule.

- Under **AND**, `relationship` ∩ `member_type=scout` = ∅ — parents aren't scouts, so the
  group silently empties.
- Under **OR**, it dumps unrelated parents into the result.

It also points at *other* groups, which is rarely what a leader means. The real intent is
almost always: "this group's members **and their parents**."

### Design

Replace the `relationship` **dimension** with a boolean on the group:

```
Group.include_parents    Boolean   NOT NULL   DEFAULT False   server_default 'false'
```

Resolution becomes a two-phase pipeline:

```
resolved = live( manual ∪ combine_rules(rule_logic) )     # phase 1 — unchanged
if group.include_parents:
    resolved = live( resolved ∪ parents_of(resolved) )    # phase 2 — new
return frozenset(resolved)
```

`parents_of(set)` is the existing `_parents_of` helper (members with a `parent_of` /
`guardian_of` relationship *to* anyone in the set). It moves from a rule evaluator to a
post-resolution step. Parents are added to the **final** resolved set — after manual ∪
dynamic — so the toggle reads as "...and their parents/guardians" regardless of how the
core membership was built.

### Removed: `RuleDimension.RELATIONSHIP`

- Drop `RELATIONSHIP` from the `RuleDimension` enum.
- Remove the `relationship` case from `evaluate_rule` (keep `_parents_of`).
- Remove relationship validation from `PUT /groups/{id}/rules/{dimension}`.

### Interactions to get right

- **`member_group_ids` (inverse resolution).** A parent is now a member of every
  `include_parents` group that resolves a member they're a parent/guardian of. The inverse
  must account for this so **event visibility** and the **iCal feed** treat parents as
  group members. Concretely: after computing a member's manual + rule-matched groups, also
  add any `include_parents` group whose phase-1 resolution contains a child the member is a
  parent/guardian of.
- **No new cycle risk.** Parents-of is a single non-recursive hop over the *already
  resolved* set; the existing `group_member` cycle guard still covers rule recursion.
- **Self-reference is now natural.** "This group's members plus their parents" needs no
  target group — the old self-reference rejection for `relationship` goes away with the
  dimension.

### Migration

Pre-production data only, and the old `relationship` semantic ("parents of a *different*
target group") does not map cleanly to the new one ("parents of *this* group"). Migration:

1. Add `include_parents` (default false).
2. For any group that has a non-deleted `relationship` rule, set `include_parents = True`.
   *(Caveat: where the rule targeted a different group, this approximates rather than
   preserves intent. Acceptable given no production data; called out so it isn't a silent
   behavior change.)*
3. Soft-delete / drop all `relationship` `GroupRule` rows.
4. Remove `RELATIONSHIP` from the enum (DB stores the string, so no type migration beyond
   deleting the rows; confirm no CHECK constraint pins the enum values).

---

## 2. Modern "filter → bubble" rule editor

### Goals (from current pain points)

- **Keep-open multi-select.** Picking a position should *not* close the popover. The
  picker stays open with a search box and per-row checkmarks so you can add several
  positions/groups in a row, then dismiss. (Today every selection calls `setAddPosOpen(false)`.)
- **Type-ahead everywhere there are many choices** (positions especially) — already uses
  `Command` + `CommandInput`; preserve and make consistent.
- **Selected values render as removable chips** (`Badge` + `×`). Positions and groups
  already do this; make it the uniform pattern and keep selected items visible while the
  picker stays open.
- **Unified builder feel** rather than a stack of bordered checkbox rows.

### Approach

Reuse existing shadcn primitives already in the tree (`Command`, `Popover`, `Badge`) — no
new dependencies.

- A reusable **`MultiSelectChips`** component: a chip row of current selections (each with
  an `×`), plus an "Add…" `Popover` containing a `Command` with `CommandInput` search and
  `CommandItem`s that show a check when selected and **do not close on select**. Used for
  positions and group-membership dimensions.
- Enum dimensions (member type, membership status) keep inline checkbox chips but adopt the
  same chip styling for consistency.
- Boolean dimensions (OA member, OA active) and the new **Include parents/guardians**
  toggle are simple switches/checkboxes.
- The top-level **AND/OR ("Match ALL / Match ANY")** control stays where it is.
- The **Include parents/guardians of these members** toggle sits *below* the rules, visually
  separated, to reinforce that it applies *after* the rules resolve. Label copy e.g.:
  *"Also include the parents/guardians of everyone above."*
- Keep the live **"Resolved members: N"** count; it now reflects the parent expansion.

This is the largest chunk of work but is purely frontend and uses in-repo components.

---

## 3. Group types: `manual` + `dynamic` → `custom`

### Design

```python
class GroupType(enum.StrEnum):
    PATROL = "patrol"
    CUSTOM = "custom"
```

- `GroupType` default becomes `CUSTOM` (was `MANUAL`) in the model and `GroupBase`.
- A **`custom`** group supports both manual member adds **and** dynamic rules — the
  resolver already does this; we simply stop gating it in the UI.
- **`patrol`** keeps its rules: at most one patrol per member (enforced via
  `_clear_patrol_membership`), adults excluded. Patrols may still carry rules (unchanged
  from the prior spec's "no type restrictions" principle), but the common case is manual.

### Resolver

No change. `resolve_group_members` already unions manual + rules for every type.

### Migration

1. Map existing `group_type`: `manual` → `custom`, `dynamic` → `custom`; `patrol` unchanged.
2. Update the model default and `SAEnum` value set.
3. Confirm no DB CHECK/enum constraint pins the old string values (SQLite tests use the
   string values; Postgres uses `SAEnum(values_callable=...)` — verify the migration
   updates any native enum type or that none is used).

### UI

- **Type selector** (edit + `new` pages): two options — **Patrol** and **Custom** (was
  Patrol / Manual group / Dynamic group).
- **Drop the `group_type !== "dynamic"` gates** that hide manual add, and the
  `group_type === "dynamic"` gates that hide rules. For `custom`, show **both** the
  Members section (manual add) and the Rules section.
- For `patrol`, show the Members section; rules optional/secondary.
- Update type labels, badges, and icons (`groups/page.tsx`, `members/columns.tsx`,
  `group-membership-editor.tsx`, `group-detail-sheet.tsx`) to the two-value set. Pick a
  `custom` icon (e.g. reuse a neutral list/users glyph; the `Zap` "dynamic" icon retires).

---

## Deferred: per-filter AND/OR

Not built now. Arbitrary per-filter operators are ambiguous without explicit grouping
("A AND B OR C" has two meanings). The expectation is that removing the relationship wart
(#1) makes the single top-level AND/OR sufficient. If a concrete unmet case appears, adopt
a constrained **disjunctive-normal-form** model — *"Match **any** of these rule sets, where
each set matches **all** of its filters"* (Mailchimp-style) — never an arbitrary nested
boolean tree. Tracked here so the decision is explicit.

---

## Changes to existing code

### Backend

| File | Change |
|------|--------|
| `app/models/enums.py` | `GroupType` → `{PATROL, CUSTOM}`; remove `RELATIONSHIP` from `RuleDimension`. |
| `app/models/group.py` | Add `Group.include_parents` (Boolean, default False, server_default). Default `group_type` → `CUSTOM`. |
| `app/schemas/group.py` | `GroupBase.group_type` default `CUSTOM`; add `include_parents` to `GroupBase`/`GroupUpdate`/`GroupRead`. |
| `app/core/groups.py` | Phase-2 parent expansion in `resolve_group_members`; remove `RELATIONSHIP` case from `evaluate_rule` (keep `_parents_of`); update `member_group_ids` to credit parents into `include_parents` groups. |
| `app/routers/groups.py` | Remove `RELATIONSHIP` from rule validation; patrol/adult checks unchanged. |
| `app/importers/twh.py` | Patrols still import as `group_type=patrol`; no manual/dynamic produced — confirm no literal `"manual"`/`"dynamic"`. |
| `backend/alembic/` | Migration: add `include_parents`; remap `group_type` values; set `include_parents` from relationship rules then drop them. RLS already enabled on `groups`/`group_rules`. |

### Frontend (`apps/web/`)

| File | Change |
|------|--------|
| `src/types/api.ts` | `GroupType` → `"patrol" \| "custom"`; drop `"relationship"` from `RuleDimension`; add `include_parents` to `Group`. |
| `src/app/(dashboard)/groups/[id]/edit/page.tsx` | New bubble builder; keep-open multi-select; `include_parents` toggle; drop dynamic/manual gates; remove relationship rule row. |
| `src/app/(dashboard)/groups/new/page.tsx` | Two-value type selector; same builder; pass `include_parents`. |
| `src/components/group-membership-editor.tsx` | Replace `group_type !== "dynamic"` logic with custom/patrol; new icon/label. |
| `src/app/(dashboard)/groups/page.tsx`, `members/columns.tsx`, `groups/group-detail-sheet.tsx` | Two-value labels/badges/icons; drop relationship-dimension display. |
| `src/hooks/use-groups.ts` | Thread `include_parents` through create/update. |
| New: `src/components/multi-select-chips.tsx` | Reusable keep-open, searchable, chip-based multi-select. |

### Tests

- Resolution: parent expansion on/off; parents added after manual ∪ dynamic; `include_parents`
  with empty group is a no-op.
- `member_group_ids`: a parent is reported in an `include_parents` group; event-visibility
  and iCal reflect it.
- Removal of `relationship`: `PUT /groups/{id}/rules/relationship` now 422s (unknown enum).
- Group type: create/update with `custom`; `manual`/`dynamic` rejected (or migrated);
  patrol one-per-member + adult exclusion still enforced.
- Migration test for the value remap if feasible in the SQLite harness.
- **Per the repo convention, the relationship-shape bug (#1) gets a regression test that
  would have caught the AND-empties-the-group behavior.**

---

## Open Questions

1. **`custom` type label/icon.** "Custom" in copy; which lucide icon replaces `Zap`?
   (Proposal: a neutral `Users`/`List` glyph.)
2. **Patrol + rules in the UI.** Keep rules available on patrols (per prior spec) or hide
   them to keep the patrol editor simple? (Proposal: keep available but de-emphasized.)
3. **Migration faithfulness for old `relationship` rules** targeting a *different* group —
   approximate via `include_parents=True` (proposed) vs. drop silently. Pre-prod, so low
   stakes.
