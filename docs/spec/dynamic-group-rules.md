# Dynamic Group Rules Spec

**Status:** Draft
**Routes:** `/groups/{id}/rules` (API) · `/groups/{id}/edit` (rule editor UI)
**Pillar:** Roster & Relationships (Pillar 1) — Groups & Audiences
**Related:** [`groups-screen.md`](groups-screen.md) · [`roles-rbac.md`](roles-rbac.md) · [`group-subscriptions.md`](group-subscriptions.md)
**Supersedes:** the current `GroupPositionRule` model (position-only dynamic rules)

---

## Overview

Today, a group's dynamic membership is limited to **position-based rules** —
`GroupPositionRule` maps a position to a group, and anyone holding that position is a
member. This covers the PLC use case (Patrol Leaders + SPL + ASM + SM) but not the
broader range of dynamic groups that troop leaders need:

- **"All adults"** — a distribution list for committee emails
- **"All OA members"** — for Order of the Arrow communications
- **"Parents of scouts in Eagle Patrol"** — parents of scouts in a specific patrol
- **"All active scouts"** — for event visibility
- **"Everyone with rank ≥ Star"** — for high-adventure eligibility

Rather than adding one-off rule tables per dimension, this spec introduces a **general-
purpose rule engine** where each rule is a typed predicate with a dimension (what field to
match) and a set of values (what to match against). Groups can combine **manual members**
and **any number of rules**. A per-group **AND/OR toggle** (`rule_logic`) controls how
rules combine:

- **AND (default):** a member must match *all* rules to be included. "Active scouts who
  are OA members" = `member_type=scout` AND `oa_member`. Each rule narrows the set.
- **OR:** a member matching *any* rule is included. "Adults or leadership-position
  holders" = `member_type=adult` OR `position=SPL,SM`. Each rule broadens the set.

Manual members (`GroupMember` rows) are **always included regardless of rule logic** —
they are unioned in after rule evaluation.

### Design principle: no group type restrictions

Currently `GroupType` has three values: `manual`, `dynamic`, `patrol`. The current
groups screen forbids users from creating `dynamic` groups (line 133 of groups-screen.md).
With this feature, **every group (including patrols) can have rules attached**. The
`GroupType` becomes purely a management/UI hint — a patrol is still a patrol (one-per-
member constraint), but it can additionally have rules if the troop wants (e.g., "all
scouts" auto-assigned to a "Whole Troop" patrol for billing purposes). The groups-screen
spec already states: *"Resolution always unions manual inclusions with any rule-derived
members, regardless of type; the type is a management/UI hint, not a hard switch."*

---

## Rule Dimensions

Each rule targets one **dimension** of a member's data. The supported dimensions are:

| Dimension | Enum value | Match semantics | Values | Available at launch? |
|-----------|-----------|----------------|--------|---------------------|
| **Member type** | `member_type` | `member.member_type IN values` | `scout`, `adult` | ✅ Yes |
| **Membership status** | `membership_status` | `member.membership_status IN values` | `active`, `inactive`, `alumni` | ✅ Yes |
| **Is OA member** | `oa_member` | `member.oa_member = True` | *(no values — boolean)* | ✅ Yes |
| **Is OA active** | `oa_active` | `member.oa_active = True` | *(no values — boolean)* | ✅ Yes |
| **Position** | `position` | member holds any of the named positions | UUID list (position IDs) | ✅ Yes (replaces `GroupPositionRule`) |
| **Patrol / group membership** | `group_member` | member is in any of the named groups | UUID list (group IDs) | ✅ Yes |
| **Relationship** | `relationship` | member has a `parent_of` or `guardian_of` relationship to any resolved member of a target group | UUID list (group IDs — the child groups) | ✅ Yes |
| **Rank** | `rank` | member's current rank is in the selected set | String list (rank names) | ⏳ Phase 2 (blocked on Pillar 4 — no `Rank` model yet) |

### Boolean dimensions

`oa_member` and `oa_active` are simple boolean flags — the rule has no `values` payload.
The rule matches all members where `member.<dimension> = True`.

### Relationship dimension ("parent of" rule)

The `relationship` dimension answers: "include every member who is a parent/guardian of
someone in group X." Resolution:

1. Resolve the target group(s) to get child member IDs.
2. Find all `MemberRelationship` rows where `to_member_id IN child_ids` and
   `relationship_type IN (parent_of, guardian_of)`.
3. Return the `from_member_id` set.

This enables the "parents of Eagle Patrol" use case. Because it resolves through the
group system, it composes: "parents of [dynamic group: all active scouts]" works
transitively.

> [!WARNING]
> **Circular reference guard:** A group rule referencing itself (directly or transitively)
> via `group_member` or `relationship` would cause infinite recursion. The resolver must
> detect and break cycles (see [Resolution Algorithm](#resolution-algorithm)).

### Rank dimension (Phase 2 placeholder)

The advancement data model (Pillar 4) is not yet built. When `Rank` and
`MemberRankCompletion` models exist, this dimension will match members whose current rank
is in the selected set. The rule infrastructure supports it now — the dimension enum
includes `rank`, and the resolver will skip it with a warning if the model doesn't exist.
The UI will hide the rank dimension until Pillar 4 lands.

---

## Data Model

### Replace `GroupPositionRule` → `GroupRule`

The current `GroupPositionRule` (one table, one dimension) is replaced by a general-
purpose `GroupRule` table that stores rules for any dimension.

#### `Group.rule_logic` field

Add to the existing `Group` model:

```
rule_logic    Enum(RuleLogic)    NOT NULL  DEFAULT 'and'
```

```python
class RuleLogic(enum.StrEnum):
    AND = "and"
    OR = "or"
```

#### `GroupRule` table

```
GroupRule (TrackedBase)
├── group_id        FK → groups.id        NOT NULL
├── dimension       Enum(RuleDimension)   NOT NULL     -- what to match
├── values          JSON                  NULLABLE     -- dimension-specific payload
└── UniqueConstraint(group_id, dimension, name="uq_group_rules_group_dimension")
```

> [!IMPORTANT]
> The `UniqueConstraint` on `(group_id, dimension)` means each group has **at most one
> rule per dimension**. Multiple values for a dimension (e.g., positions PL + SPL + SM)
> are stored as a list in the `values` JSON field, not as separate rows. This simplifies
> resolution (one query per dimension) and makes rule management straightforward in the UI
> (one toggle/selector per dimension, not a list of rule rows to manage).

#### `RuleDimension` enum

```python
class RuleDimension(enum.StrEnum):
    MEMBER_TYPE = "member_type"
    MEMBERSHIP_STATUS = "membership_status"
    OA_MEMBER = "oa_member"
    OA_ACTIVE = "oa_active"
    POSITION = "position"
    GROUP_MEMBER = "group_member"
    RELATIONSHIP = "relationship"
    RANK = "rank"  # Phase 2 — no-op until Pillar 4
```

#### `values` field semantics

| Dimension | `values` content | Example |
|-----------|-----------------|---------|
| `member_type` | `["scout"]` or `["adult"]` or `["scout", "adult"]` | `["scout"]` |
| `membership_status` | `["active"]` or `["active", "inactive"]` | `["active", "alumni"]` |
| `oa_member` | `null` (boolean — presence of the rule is the predicate) | `null` |
| `oa_active` | `null` | `null` |
| `position` | `["<uuid>", "<uuid>"]` — position IDs | `["abc-123", "def-456"]` |
| `group_member` | `["<uuid>", "<uuid>"]` — group IDs | `["abc-123"]` |
| `relationship` | `["<uuid>", "<uuid>"]` — target group IDs | `["abc-123"]` |
| `rank` | `["Star", "Life", "Eagle"]` — rank names | `["Star", "Life"]` |

### Migration strategy

1. Create the `group_rules` table.
2. Migrate existing `GroupPositionRule` rows → `GroupRule` rows with
   `dimension = "position"` and `values = [position_id_1, position_id_2, ...]` (aggregate
   all position rules for a group into one `GroupRule` row).
3. Drop the `group_position_rules` table.
4. Update `Group.position_rules` relationship → `Group.rules` relationship.

---

## Resolution Algorithm

`resolve_group_members(group_id, session)` remains the single entry point. The algorithm
changes to:

```
resolve_group_members(group_id, session, _visited=None):
    if group_id in _visited: return frozenset()  # cycle guard
    _visited.add(group_id)

    # 1. Manual members (GroupMember rows) — always included
    manual = manual_members(group_id)

    # 2. Evaluate each rule independently
    rule_sets = []
    for rule in group_rules(group_id):
        match rule.dimension:
            case MEMBER_TYPE:
                rule_sets.append(members_by_type(rule.values))
            case MEMBERSHIP_STATUS:
                rule_sets.append(members_by_status(rule.values))
            case OA_MEMBER:
                rule_sets.append(members_where(oa_member=True))
            case OA_ACTIVE:
                rule_sets.append(members_where(oa_active=True))
            case POSITION:
                rule_sets.append(members_holding_positions(rule.values))
            case GROUP_MEMBER:
                combined = set()
                for ref_group_id in rule.values:
                    combined |= resolve_group_members(ref_group_id, session, _visited)
                rule_sets.append(combined)
            case RELATIONSHIP:
                combined = set()
                for ref_group_id in rule.values:
                    child_ids = resolve_group_members(ref_group_id, session, _visited)
                    combined |= parents_of(child_ids)
                rule_sets.append(combined)
            case RANK:
                pass  # Phase 2

    # 3. Combine rule results based on group.rule_logic
    if not rule_sets:
        dynamic = set()
    elif group.rule_logic == AND:
        dynamic = set.intersection(*rule_sets)
    else:  # OR
        dynamic = set.union(*rule_sets)

    # 4. Union manual + dynamic, then filter to non-deleted members
    return live_members(manual | dynamic)
```

### Cycle detection

The `_visited` set (defaulting to `set()` on initial call) prevents infinite recursion.
If a group references itself (directly or through a chain), the recursive call returns
`frozenset()` for the already-visited group. This is safe — it just means the circular
reference contributes no additional members.

### `member_group_ids` (inverse resolution)

The inverse function also needs updating. For dimensions that don't reference other groups
(`member_type`, `membership_status`, `oa_member`, `oa_active`, `position`), we can
evaluate the member's attributes directly and collect matching group IDs. For
`group_member` and `relationship`, we must resolve transitively (with cycle detection).

### Performance considerations

- **Most rules are simple attribute checks** (`member_type = 'scout'`) that translate to
  indexed WHERE clauses — no concern.
- **Position rules** join through `MemberPositionAssignment` — same query as today.
- **Group-of-groups** and **relationship** rules recurse, but troop group counts are
  small (typically < 30). The `_visited` set bounds recursion to O(groups).
- **Caching:** For hot paths (event visibility filtering, iCal feeds), we can cache
  resolved memberships with a short TTL. Not needed for Phase 1 — the user base is small
  enough that resolution per request is fine.

---

## API Changes

### New routes: `/groups/{id}/rules`

Replace the existing `/groups/{id}/rules` endpoints (which are position-specific) with
general-purpose rule CRUD:

| Method | Path | Body | Description |
|--------|------|------|-------------|
| `GET` | `/groups/{id}/rules` | — | List all rules for this group |
| `PUT` | `/groups/{id}/rules/{dimension}` | `{ "values": [...] }` | Create or update a rule for this dimension |
| `DELETE` | `/groups/{id}/rules/{dimension}` | — | Remove a rule for this dimension |

**Why PUT instead of POST+PATCH:** Since each dimension has at most one rule per group
(the unique constraint), `PUT` is the natural idempotent upsert. If the rule exists, it
updates the values; if not, it creates it. This matches the UI pattern: the user toggles
a dimension on and picks values — one action.

#### Request/response schemas

```python
class GroupRuleRead(TrackedRead):
    group_id: uuid.UUID
    dimension: RuleDimension
    values: list[str] | None = None

class GroupRuleUpsert(BaseModel):
    values: list[str] | None = None
```

#### Validation

- `PUT` validates that `values` is appropriate for the dimension:
  - Boolean dimensions (`oa_member`, `oa_active`): `values` must be `null` or omitted.
  - Enum dimensions (`member_type`, `membership_status`): each value must be a valid enum
    member.
  - FK dimensions (`position`, `group_member`, `relationship`): each UUID must reference
    a real, non-deleted, same-tenant record. Self-referencing group IDs are rejected
    (immediate cycle detection at write time).
  - `rank`: each value must be a string. No FK validation until Pillar 4.
- `DELETE` is idempotent — returns 204 whether the rule existed or not.

---

## UI: Rule Editor

The rule editor is a section on the **group edit page** (`/groups/{id}/edit`), shown for
all group types (not just `dynamic`). It replaces the current "Position Rules" section.

### Layout

```
Rules (dynamic membership)
─────────────────────────────────────────────────

Each rule adds members automatically. Members from all rules
are combined with any manually added members.

┌────────────────────────────────────────────────┐
│ ☑ Member type          [Scout ▾] [Adult ▾]     │
├────────────────────────────────────────────────┤
│ ☐ Membership status                            │
├────────────────────────────────────────────────┤
│ ☑ Is OA member                                 │
├────────────────────────────────────────────────┤
│ ☐ Is OA active                                 │
├────────────────────────────────────────────────┤
│ ☑ Has position         [Patrol Leader ×]       │
│                        [SPL ×]                 │
│                        [+ Add position…]       │
├────────────────────────────────────────────────┤
│ ☐ Is member of group                           │
├────────────────────────────────────────────────┤
│ ☐ Parent/guardian of group                     │
├────────────────────────────────────────────────┤
│ ☐ Has rank (coming soon)                       │
└────────────────────────────────────────────────┘

Resolved members: 12
```

### Interaction

- Each dimension is a **row with a checkbox** (toggle). Enabling it creates the rule via
  `PUT /groups/{id}/rules/{dimension}`. Disabling it deletes via `DELETE`.
- Dimensions with values show a multi-select picker when enabled:
  - Enum dimensions: checkbox group (e.g., checkboxes for Scout / Adult)
  - FK dimensions: combobox with search (positions, groups)
- Changes save immediately (same pattern as group membership — no batching).
- The "Resolved members: N" count updates after each rule change.
- The rank dimension row shows "(coming soon)" and is disabled.

### Group create page

The create page (`/groups/new`) should also show the rule editor section. This enables
creating a fully configured dynamic group in one flow — the user picks a name, type,
color, and rules all on one page. Rules are saved after the group is created (sequential
API calls: `POST /groups/` then `PUT /groups/{id}/rules/{dim}` for each enabled rule).

---

## Shared code opportunity: reporting

The rule dimensions map naturally to **report filters**. When the report builder (Pillar 5)
is implemented, the same dimension enum and evaluation logic can power report scoping:

- "Roster report for all active scouts" → `member_type = scout` + `membership_status = active`
- "Contact list for parents of Eagle Patrol" → `relationship` dimension targeting Eagle Patrol

To enable this:

1. Extract the per-dimension member filtering into a standalone function:
   `evaluate_rule(dimension, values, session) → set[member_id]`
2. `resolve_group_members` calls `evaluate_rule` for each `GroupRule`.
3. The future report builder calls `evaluate_rule` directly with user-supplied filters.

This is designed into the architecture now but the report builder itself is a future
concern.

---

## Changes to existing code

### `app/models/group.py`

- Remove `GroupPositionRule` class.
- Add `GroupRule` class.
- Update `Group.position_rules` → `Group.rules` relationship.

### `app/models/enums.py`

- Add `RuleDimension` enum.

### `app/schemas/group.py`

- Remove `GroupPositionRuleCreate`, `GroupPositionRuleRead`.
- Add `GroupRuleRead`, `GroupRuleUpsert`.

### `app/core/groups.py`

- Rewrite `resolve_group_members` to iterate `GroupRule` rows by dimension.
- Add `evaluate_rule(dimension, values, session)` helper.
- Update `member_group_ids` for the new rule types.

### `app/routers/groups.py`

- Replace `/rules` endpoints (position-specific → dimension-generic).
- Update imports and schemas.

### `backend/alembic/`

- New migration: create `group_rules`, migrate `group_position_rules` data, drop old table.

### Frontend (`apps/web/`)

- Update groups hooks (`use-groups.ts`) for new rule API shape.
- Build rule editor component on group edit page.
- Update group detail sheet to show rules by dimension (not just positions).
- Update `types/api.ts` for new schemas.

### Tests

- Update `test_groups_resolution.py` for new rule dimensions.
- Update `test_api_groups.py` for new rule API.
- Add tests for cycle detection, relationship resolution, boolean dimensions.

---

## Open Questions

1. **Negation rules?** Should a rule be invertible — e.g., "NOT OA member" or "NOT in
   Eagle Patrol"? This adds complexity. Recommendation: defer — leaders can create the
   positive group and use it for exclusion in messaging/reports.

2. **Rule ordering / priority?** With both AND and OR, ordering doesn't matter (both are
   commutative). No ordering needed.
