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
   empties the group). It is replaced by **two distinct, post-resolution parent options**
   (membership vs. communications — see [§1](#1-parentsguardians-two-distinct-options)).
2. **The rule editor UI feels dated.** Move to a modern "filter → bubble" builder with
   type-ahead, keep-open multi-select pickers, and removable chips.
3. **Per-filter AND/OR mixing — deferred.** Once #1 removes the relationship wart, the
   single top-level AND/OR is expected to suffice. Revisit with a Mailchimp-style
   "OR of AND-groups" model only if a concrete unmet need appears (see
   [Deferred](#deferred-per-filter-andor)).
4. **Collapse `manual` + `dynamic` group types into one `custom` type.** The resolver
   already unions manual members with rules regardless of type; the manual/dynamic split
   is a UI gate only. A `custom` group supports **both** manual adds and dynamic rules.
   `patrol` stays distinct (one-per-member, adults excluded) and gets **no rules**.

Items #1, #2, and #4 ship together; they reinforce each other (a `custom` group's
parent options naturally apply to its full manual + dynamic membership).

---

## 1. Parents/Guardians: two distinct options

### Problem

`relationship` is today a `RuleDimension`: it takes target group IDs and contributes
"parents of those groups' members" into the same AND/OR pool as every other rule.

- Under **AND**, `relationship` ∩ `member_type=scout` = ∅ — parents aren't scouts, so the
  group silently empties.
- Under **OR**, it dumps unrelated parents into the result.

It also points at *other* groups, which is rarely what a leader means. The real intent is
"this group's members **and their parents**" — but there are actually **two different
intents** hiding in that phrase:

1. **Parents as members** — parents *belong to* the group. They show up in membership,
   see the group's events, get it on their iCal, and are scoped into future reports.
2. **Parents on communications** — parents are *not* members, but messages sent to the
   group also reach them. This is a messaging-recipient concern, not a membership one.
   (Canonical case: a **patrol** — its roster is scouts, but patrol announcements should
   also reach parents. Parents must **not** become patrol members.)

### Design — two independent booleans

```
Group.include_parents          Boolean  NOT NULL  DEFAULT False  server_default 'false'
Group.cc_parents_on_messages   Boolean  NOT NULL  DEFAULT False  server_default 'false'
```

**`include_parents` (membership).** Available on **custom** groups only. Resolution gains a
post-resolution phase:

```
resolved = live( manual ∪ combine_rules(rule_logic) )     # phase 1 — unchanged
if group.include_parents:
    resolved = live( resolved ∪ parents_of(resolved) )    # phase 2 — new
return frozenset(resolved)
```

`parents_of(set)` is the existing `_parents_of` helper (members with a `parent_of` /
`guardian_of` relationship *to* anyone in the set). It moves from a rule evaluator to a
post-resolution step, added to the **final** set — after manual ∪ dynamic — so it reads as
"...and their parents/guardians" regardless of how the core membership was built.

**`cc_parents_on_messages` (communications).** Available on **both custom and patrol**
groups. It does **not** affect `resolve_group_members`, visibility, or iCal — membership is
unchanged. The future Messaging layer (Pillar 2) expands recipients:

```
recipients = resolve_group_members(group)
if group.cc_parents_on_messages:
    recipients |= parents_of(resolve_group_members(group))
```

This composes idempotently with `include_parents` (members already include parents, so the
union is a no-op there).

> [!NOTE]
> **No consumer yet.** Messaging is unbuilt (Pillar 2, draft). `cc_parents_on_messages` is
> stored now and surfaced in the UI with a "used when you message this group (coming soon)"
> hint — the same pattern as the Rank "coming soon" rule. If `include_parents` is on, the
> comms checkbox is implied and shown disabled/checked so the two are never contradictory.

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
  parent/guardian of. `cc_parents_on_messages` is **not** consulted here — it is messaging-only.
- **No new cycle risk.** Parents-of is a single non-recursive hop over the *already
  resolved* set; the existing `group_member` cycle guard still covers rule recursion.
- **Self-reference is now natural.** "This group's members plus their parents" needs no
  target group — the old self-reference rejection for `relationship` goes away with the
  dimension.

### Migration

Pre-production — **no real data exists**, so the old `relationship` rules are dropped
silently (their "parents of a *different* group" semantic does not map to the new options
and isn't worth preserving):

1. Add `include_parents` and `cc_parents_on_messages` (both default false).
2. Soft-delete / drop all `relationship` `GroupRule` rows. **Do not** set either new flag
   from them.
3. Remove `RELATIONSHIP` from the enum (DB stores the string, so no type migration beyond
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
- The two **parent options** sit *below* the rules, visually separated, to reinforce that
  they apply *after* the rules resolve:
  - **Include parents/guardians as members** (custom only) — *"Also add the
    parents/guardians of everyone above to this group."*
  - **Send messages to parents/guardians** (custom + patrol) — *"When you message this
    group, also include parents/guardians (coming soon)."* Shown disabled-and-checked when
    membership-parents is on (implied).
- Keep the live **"Resolved members: N"** count; it now reflects the `include_parents`
  expansion (but **not** `cc_parents_on_messages`, which doesn't change membership).

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
  resolver already does this; we simply stop gating it in the UI. It exposes both parent
  options (`include_parents`, `cc_parents_on_messages`). Icon: a neutral `Users`/`List`
  glyph (the `Zap` "dynamic" icon retires).
- **`patrol`** keeps its constraints: at most one patrol per member (enforced via
  `_clear_patrol_membership`), adults excluded. **Patrols have no rule editor** — membership
  is manual only. The one parent option a patrol exposes is `cc_parents_on_messages`
  (comms), never `include_parents` (parents must not become patrol members). This reverses
  the prior spec's "any type can have rules" principle for patrols specifically.

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

## UI cache invalidation (staleness fixes)

Group membership changes sometimes don't reflect immediately in the UI. Root cause:
React Query cache invalidation in `use-groups.ts` (and sibling hooks) is **too narrow**
for a resolution graph that is transitive. A group's resolved membership can depend on:
other groups (`group_member` rules), members' attributes (`member_type`, `oa_*`, status),
position assignments (`position` rule), the group's own `rule_logic` / `include_parents`,
and parent/guardian relationships. So a change in one place can change *any* group's
membership — yet several mutations invalidate only one group, or nothing group-related.

The fix is to make every mutation that can affect resolution invalidate the **whole**
`[tenantId, "group-members"]` key (the pattern `useAddGroupMember` / `useUpdateMember`
already use). The derived hooks (`useGroupMemberCounts`, `useGroupMemberships`,
`usePatrolMemberships`, `useMemberGroups`) all read from that key, so one broad
invalidation refreshes counts, badges, and rosters together.

### Confirmed gaps to fix

| Hook | Today | Fix |
|------|-------|-----|
| `useUpdateGroup` | invalidates `["groups"]`, `["groups", id]` only | **Also invalidate `["group-members"]`** — `rule_logic` (AND↔OR) and `include_parents` change resolved membership. *(Primary suspect for the reported symptom.)* |
| `useUpsertGroupRule` / `useDeleteGroupRule` | invalidate `["group-members", groupId]` (single group) | **Broaden to `["group-members"]`** — groups referencing this one via `group_member` / parents-of are otherwise stale. Keep `["group-rules", groupId]`. |
| `useAssignMemberPosition` / `useRemoveMemberPosition` (`use-member-positions.ts`) | invalidate `member-positions`, `session` | **Add `["group-members"]`** — position rules depend on assignments (e.g. PLC). |
| Relationship edits (when a mutation hook exists) | n/a — no hook today | Once relationship editing ships, it must invalidate `["group-members"]` because `include_parents` resolution depends on `parent_of` / `guardian_of` links. *(Forward-looking note.)* |

`cc_parents_on_messages` does **not** change membership, so it needs no `group-members`
invalidation (only `["groups"]` / `["groups", id]`).

### Tests

- These are bug fixes → **each gets a test** (repo convention). For the hooks above, assert
  the mutation's `onSuccess` invalidates `["group-members"]` (e.g. spy on
  `queryClient.invalidateQueries`, or drive it through Testing Library and assert the
  refetch). Cover at minimum: AND↔OR toggle, `include_parents` toggle, a rule upsert seen
  by a dependent group-of-groups, and a position assignment seen by a position-rule group.

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
| `app/models/group.py` | Add `Group.include_parents` and `Group.cc_parents_on_messages` (Boolean, default False, server_default). Default `group_type` → `CUSTOM`. |
| `app/schemas/group.py` | `GroupBase.group_type` default `CUSTOM`; add `include_parents` + `cc_parents_on_messages` to `GroupBase`/`GroupUpdate`/`GroupRead`. |
| `app/core/groups.py` | Phase-2 `include_parents` expansion in `resolve_group_members`; remove `RELATIONSHIP` case from `evaluate_rule` (keep `_parents_of`); update `member_group_ids` to credit parents into `include_parents` groups. `cc_parents_on_messages` is **not** referenced here. |
| `app/routers/groups.py` | Remove `RELATIONSHIP` from rule validation; patrol/adult checks unchanged. Optionally reject rule writes on `patrol` groups (patrols have no rules). |
| `app/importers/twh.py` | Patrols still import as `group_type=patrol`; no manual/dynamic produced — confirm no literal `"manual"`/`"dynamic"`. |
| `backend/alembic/` | Migration: add `include_parents` + `cc_parents_on_messages`; remap `group_type` (`manual`/`dynamic` → `custom`); drop all `relationship` rules silently. RLS already enabled on `groups`/`group_rules`. |

### Frontend (`apps/web/`)

| File | Change |
|------|--------|
| `src/types/api.ts` | `GroupType` → `"patrol" \| "custom"`; drop `"relationship"` from `RuleDimension`; add `include_parents` + `cc_parents_on_messages` to `Group`. |
| `src/app/(dashboard)/groups/[id]/edit/page.tsx` | New bubble builder; keep-open multi-select; both parent toggles; rules + manual members shown together for `custom`; **no rule editor for `patrol`** (only `cc_parents_on_messages`); remove relationship rule row. |
| `src/app/(dashboard)/groups/new/page.tsx` | Two-value type selector; same builder; pass both parent flags. |
| `src/components/group-membership-editor.tsx` | Replace `group_type !== "dynamic"` logic with custom/patrol; new icon/label. |
| `src/app/(dashboard)/groups/page.tsx`, `members/columns.tsx`, `groups/group-detail-sheet.tsx` | Two-value labels/badges/icons; drop relationship-dimension display. |
| `src/hooks/use-groups.ts` | Thread both parent flags through create/update; broaden cache invalidation (see [UI cache invalidation](#ui-cache-invalidation-staleness-fixes)) — `useUpdateGroup`, `useUpsertGroupRule`, `useDeleteGroupRule`. |
| `src/hooks/use-member-positions.ts` | `useAssignMemberPosition` / `useRemoveMemberPosition` also invalidate `["group-members"]`. |
| New: `src/components/multi-select-chips.tsx` | Reusable keep-open, searchable, chip-based multi-select. |

### Tests

- Resolution: `include_parents` on/off; parents added after manual ∪ dynamic; empty group
  is a no-op; `cc_parents_on_messages` alone does **not** change `resolve_group_members`.
- `member_group_ids`: a parent is reported in an `include_parents` group; event-visibility
  and iCal reflect it; `cc_parents_on_messages` does **not** add the parent here.
- Removal of `relationship`: `PUT /groups/{id}/rules/relationship` now 422s (unknown enum).
- Group type: create/update with `custom`; `manual`/`dynamic` rejected (or migrated);
  patrol one-per-member + adult exclusion still enforced; patrol cannot hold `include_parents`.
- Migration test for the value remap if feasible in the SQLite harness.
- **Per the repo convention, the relationship-shape bug (#1) gets a regression test that
  would have caught the AND-empties-the-group behavior.**

---

## Resolved Decisions

1. **`custom` icon** — neutral `Users`/`List` glyph; `Zap` retires.
2. **Patrols have no rules** — manual membership only; the only parent option is
   `cc_parents_on_messages` (comms). `include_parents` is never offered on a patrol.
3. **Old `relationship` rules** — dropped silently in migration (no real data exists).
4. **Two parent options** — `include_parents` (membership; custom only) and
   `cc_parents_on_messages` (comms; custom + patrol, stored now, consumed by Messaging later).
5. **Surface the comms checkbox now** — shown in the UI immediately with a "coming soon"
   hint (Messaging consumes it later). Not deferred.

## Open Questions

None — all decisions resolved. Ready to implement.
