# Roles & RBAC Spec

**Status:** Draft
**Pillar:** Roster & Relationships (Pillar 1) — RBAC foundation
**Related:** [`session-permissions.md`](session-permissions.md) · [`groups-screen.md`](groups-screen.md) · [`members-screen.md`](members-screen.md)
**Supersedes (data model):** the single `Role` / `RoleMembership` design currently in
`app/models/role.py`. This spec splits that one table into **Positions** and
**Functional Roles** (see [Migration](#migration-from-the-current-role-model)).

---

## Overview

This spec defines how OpenTroop decides **what a member is allowed to do inside one
troop**. It is tenant-scoped RBAC, entirely distinct from the platform/global tier
(`User.platform_role`, the SaaS control plane).

The guiding principle, stated as a hard constraint:

> **A member's _position_ dictates what they can do. The only routine assignment action
> is "give this member a position." Granting a permission — or a functional role —
> directly to an individual is a design failure we engineer against.**

Everything below follows from that. If a troop ever finds itself needing to grant
"approve advancement" to one specific person, the answer is to give that person a
**position** that carries it (positions are tenant-customizable), not to hand-edit an
individual's permissions.

---

## Terminology (canonical)

The word **"role"** is retired from domain language because it's ambiguous. We use three
precise terms, and UI strings + future specs use only these:

| Term | Definition | What you do with it | Carries |
|---|---|---|---|
| **Group** | A resolvable *set of members* for **targeting** — patrols, PLC, OA chapter. | Event visibility, messaging, report scoping | **No permissions** |
| **Position** | What a member **is** in the troop — Scoutmaster, Committee Chair, SPL, Patrol Leader. | **Assigned to a member** (the primary, near-only action) | Membership in functional roles |
| **Functional role** | A named **permission bundle** — Member Admins, Advancement Approvers, Event Admins. | Tune which permissions it carries; map positions into it | Permissions |

The authorization chain is exactly two levels deep:

```
member ──assign──▶ Position(s) ──seeded mapping──▶ Functional role(s) ──▶ Permission(s)
        (routine)                 (edited rarely)                  (edited rarely)
```

A member's effective permissions are the **union** across all positions they hold.
Composition is done by **stacking positions** (Treasurer + Parent), never by per-member
permission grants.

### Why two tables, not one

Positions and functional roles are structurally similar (both could hold permissions and
"belong to" something), which is why the current code unified them into `Role` with a
recursive resolver. But this model is deliberately **two levels deep** — it never needs
functional-role-inherits-functional-role chains. Splitting them:

- makes "only a position is assignable to a member" a **foreign key**, not a runtime
  check — closing the back-door where a functional role could be granted to an individual;
- lets the two concepts grow their own columns (positions: scout/adult applicability,
  ordering; functional roles: `is_admin`, permission set) without a nullable-heavy table;
- **simplifies the resolver** to a flat 2-hop join (the recursion in
  `resolve_permissions` exists *only* to support unbounded nesting we don't use).

The only capability given up is functional-role-to-functional-role inheritance; where that
seems wanted (Advancement Admins ⊇ Recorders) we simply list the permissions explicitly.

---

## Data model

All tables are tenant-scoped (`TrackedBase`: UUIDv7 PK, `tenant_id`, timestamps,
`is_deleted`). New `TrackedBase` tables require RLS wiring per `backend/CLAUDE.md`.

### `Position` (`positions`)

What a member is; the assignable unit.

| Field | Type | Notes |
|---|---|---|
| `name` | `str(120)` | "Scoutmaster", "Patrol Leader" |
| `slug` | `str(80)` | unique per tenant (`uq_positions_tenant_slug`) |
| `applies_to` | `PositionScope` enum | `scout` / `adult` / `any` — UI filtering & validation |
| `is_system` | `bool` | seeded defaults; cannot be deleted, can be reconfigured |
| `sort_order` | `int` | display ordering of the troop's position list |

### `FunctionalRole` (`functional_roles`)

A permission bucket.

| Field | Type | Notes |
|---|---|---|
| `name` | `str(120)` | "Member Admins" |
| `slug` | `str(80)` | unique per tenant (`uq_functional_roles_tenant_slug`) |
| `is_system` | `bool` | seeded; cannot be deleted, can be reconfigured |
| `is_admin` | `bool` | short-circuits to **all** permissions (the Administrators role) |

### `FunctionalRolePermission` (`functional_role_permissions`)

| Field | Notes |
|---|---|
| `functional_role_id` | FK → `functional_roles.id` |
| `permission` | `Permission` enum value |
|  | `uq_functional_role_permissions_role_perm (functional_role_id, permission)` |

### `PositionFunctionalRole` (`position_functional_roles`) — *the product surface*

The many-to-many mapping that makes "just assign a position" do the right thing. This
table is what ships with sensible defaults and is what a troop tunes when it wants
different governance.

| Field | Notes |
|---|---|
| `position_id` | FK → `positions.id` |
| `functional_role_id` | FK → `functional_roles.id` |
|  | `uq_position_functional_roles (position_id, functional_role_id)` |

### `MemberPositionAssignment` (`member_position_assignments`)

The one routine write. Replaces `MemberRoleAssignment`.

| Field | Notes |
|---|---|
| `member_id` | FK → `members.id` |
| `position_id` | FK → `positions.id` |
| `assigned_by_id` | FK → `members.id`, nullable — audit trail |
|  | `uq_member_position_assignments (member_id, position_id)` |

A member may hold multiple positions; soft-delete preserves history.

### Group interplay — `GroupPositionRule` (renames `GroupRoleRule`)

A dynamic Group's rule targets a **position**: "everyone holding Patrol Leader." This is
exactly the PLC use case (PL/SPL/ASM/SM). `GroupRoleRule.role_id` → `position_id`.
Targeting a *functional role* in an audience ("message all Member Admins") is derivable
later and out of scope here.

---

## Resolution

`resolve_permissions(member_id, session) -> frozenset[Permission]` becomes a flat join,
no recursion:

```
member_position_assignments  (member's live positions)
    → position_functional_roles
        → functional_role_permissions
```

Short-circuit: if any reached functional role has `is_admin=True`, return the full
`Permission` set (matches today's behavior; the frontend needs no admin special-casing).
Soft-deleted assignments, positions, mappings, roles, and permission rows are excluded at
every hop.

### Forward-compat seam: direct position permissions

**Decided:** permissions live **only** on functional roles — a position never holds a
permission directly. This stays absolute for v1 (it keeps the model clean and forces
one-off needs to become a reusable functional role rather than a snowflake).

But this *will* be requested eventually, so we plumb for it now without building it. The
resolver is written as a **union over permission sources**, not a single hardcoded walk:

```python
def resolve_permissions(member_id, session) -> frozenset[Permission]:
    sources = [
        _permissions_via_functional_roles(member_id, session),
        # _permissions_via_positions(member_id, session),  # future: direct grants
    ]
    return frozenset().union(*sources)
```

Adding direct position permissions later is then **purely additive**: introduce a
`PositionPermission` table (mirroring `FunctionalRolePermission`), implement
`_permissions_via_positions`, and uncomment one line — no caller, endpoint, or resolver
signature changes. The `is_admin` short-circuit wraps the union, so it keeps working
regardless of source. We ship only the functional-role source in v1.

`member_position_ids(member_id)` (inverse, for Group resolution and the future Positions
column on the roster) and `resolve_group_members` are updated to walk
`MemberPositionAssignment` + `GroupPositionRule` instead of the role tables.

---

## Default seed (ships with every tenant)

Seeded at provisioning (`app/core/provisioning.py`) alongside the default event types.
All rows are `is_system=True`: deletable=no, reconfigurable=yes. **These are starting
defaults — the whole point is that a troop edits the mapping, not individuals.**

### Functional roles → permissions

| Functional role | Permissions |
|---|---|
| **Administrators** | `is_admin` → all |
| **Member Admins** | member:read, member:write, member:read_contact, member:read_medical, member:write_medical, member:delete, role:assign, report:read |
| **Member Viewers** | member:read, member:read_contact |
| **Event Admins** | event:read, event:create, event:write, event:delete, event:manage_attendance, report:read |
| **Attendance Takers** | event:read, event:manage_attendance |
| **Event Viewers** | event:read |
| **Advancement Admins** | advancement:read, advancement:record, advancement:approve |
| **Advancement Recorders** | advancement:read, advancement:record |
| **Advancement Viewers** | advancement:read |
| **Finance Admins** | finance:read, finance:write, report:read |
| **Finance Viewers** | finance:read |
| **Troop Communicators** | communication:send_troop, communication:send_patrol |
| **Patrol Communicators** | communication:send_patrol |

`role:manage` (reconfigure functional roles / permissions / the mapping itself) is granted
**only** via Administrators — meta-governance stays locked. `role:assign` (assign
positions to members) rides with Member Admins so Scoutmaster/Committee Chair can manage
the roster without being full admins.

### Positions → functional roles (adult)

| Position (`applies_to=adult`) | Default functional roles |
|---|---|
| **Administrator** | Administrators |
| **Committee Chair** | Member Admins, Event Admins, Troop Communicators |
| **Chartered Org Rep (COR)** | Member Viewers |
| **Scoutmaster** | Member Admins, Event Admins, Advancement Admins, Troop Communicators |
| **Assistant Scoutmaster** | Member Viewers, Event Admins, Advancement Recorders, Troop Communicators |
| **Treasurer** | Finance Admins |
| **Advancement Chair** | Advancement Admins |
| **Membership Chair** | Member Admins |
| **Committee Member** | Member Viewers, Event Viewers |
| **Parent / Guardian** | *(none — access to their own scout comes via ReBAC, below)* |

### Positions → functional roles (scout)

| Position (`applies_to=scout`) | Default functional roles |
|---|---|
| **Senior Patrol Leader** | Event Viewers, Troop Communicators |
| **Assistant Senior Patrol Leader** | Event Viewers, Troop Communicators |
| **Patrol Leader** | Patrol Communicators |
| **Assistant Patrol Leader** | Patrol Communicators |
| **Scribe** | Attendance Takers |
| **Troop Guide / Quartermaster / Historian / Librarian / Bugler / OA Rep** | *(none by default)* |

### Administrator handling

There is no special "admin" code path beyond `FunctionalRole.is_admin`. The founder
provisioned for a new tenant is given the **Administrator position**, which maps to the
**Administrators functional role** (`is_admin=True`). Even the superuser arrives through
the normal position → functional-role → permission chain.

---

## The third axis: relationship-scoped access (ReBAC) — *designed here, built later*

RBAC answers "can you do X *at all*." It cannot express "a parent may see/edit **their
own** scout's record but no one else's," because that scoping is **per-row**, not
per-capability. This is relationship-based access (ReBAC) and is a **separate axis** from
positions/functional roles. Forcing it into a position or group would be wrong.

**Design (to implement after core RBAC lands):**

- Derived from `MemberRelationship` (`parent_of` / `guardian_of`): the adult is
  `from_member`, the youth is `to_member`.
- A new helper `app/core/access.py::can_access_member(actor_member_id, target_member_id,
  session, *, write=False)` returns true when **either** the actor holds the relevant
  `member:*` permission (RBAC) **or** the actor has a parent/guardian relationship to the
  target (ReBAC). Endpoints consult this for per-record reads/writes instead of relying on
  the coarse permission set alone.

**Decided — parents get write access.** A parent/guardian may **read and edit** both
their **own** record and their **scout's** record. Concretely, the ReBAC path grants the
same field scope a member has when editing their own record — including contact and
emergency info, **medical** fields (parents complete the BSA medical forms), and
submitting **electronic permission slips** / RSVPing on behalf of the scout. So
`can_access_member(..., write=True)` returns true for a parent→child pair, and the
relevant per-record endpoints (member edit, medical, event participation, electronic
permission) honor it. The **Parent / Guardian** position deliberately carries **no
functional role** — this relationship layer is the *only* thing granting parents access,
which keeps a parent from seeing the rest of the roster.

- **Boundary:** ReBAC scopes access to the *self + linked scouts* set only; it never
  widens to other members. A parent who is *also* a leader gets the wider roster through
  their leader **position**, not through this layer.
- Field-level carve-outs (e.g. a field only leaders may set) can be layered on later; the
  v1 default is "parent edits as if it were their own/the scout's self-service record."

This keeps the parent relationship out of RBAC while making the design coherent. It is
called out in `session-permissions.md` as "enforced at the endpoint layer," consistent
with this.

---

## API surface

Replaces the current `/roles`, `/role-memberships`, `/role-assignments` routers. All
mutations require `role:manage` except member↔position assignment, which requires
`role:assign`.

### Positions

```
GET    /positions/                      → list (member:read)
POST   /positions/                      → create custom position (role:manage)
GET    /positions/{id}                  → detail, incl. mapped functional roles (member:read)
PATCH  /positions/{id}                  → rename / applies_to / sort_order (role:manage)
DELETE /positions/{id}                  → soft-delete; 403 if is_system (role:manage)
```

### Functional roles

```
GET    /functional-roles/               → list (member:read)
POST   /functional-roles/               → create (role:manage)
GET    /functional-roles/{id}           → detail incl. permissions (member:read)
PATCH  /functional-roles/{id}           → rename (role:manage)
DELETE /functional-roles/{id}           → soft-delete; 403 if is_system (role:manage)
POST   /functional-roles/{id}/permissions    → add a Permission (role:manage)
DELETE /functional-roles/{id}/permissions/{permission}  → remove (role:manage)
```

### The mapping (position ↔ functional role)

```
POST   /positions/{id}/functional-roles       → attach a functional role (role:manage)
DELETE /positions/{id}/functional-roles/{fid} → detach (role:manage)
```

### Assigning positions to members (the routine action)

```
GET    /members/{id}/positions          → a member's positions (member:read)
POST   /members/{id}/positions          → assign a position (role:assign)
DELETE /members/{id}/positions/{pid}    → unassign (role:assign)
```

> **Deliberate omission:** there is **no** endpoint to assign a functional role or a raw
> permission to a member. The data model's only member-facing link is
> `MemberPositionAssignment`. The escape hatch (if ever needed) is creating a narrow
> custom position, not a per-member grant.

### Session

`GET /auth/session` (per `session-permissions.md`) is unchanged in shape but its `roles`
field is reinterpreted as the member's **positions** (id + name). The resolved
`permissions` set already accounts for the position → functional-role walk.

---

## Frontend

Two screens, both mirroring the Groups/Members layout conventions.

### Positions screen (`/positions`) — the everyday surface

- List of the troop's positions (system + custom), grouped by `applies_to`.
- Detail sheet shows the position's mapped functional roles and the **resolved permission
  list** (read-only, computed) so a leader sees *exactly* what holding this position
  grants — no permission spelunking.
- Assigning a position to a member happens here **and** from the member edit page
  (a `MemberPositionsEditor`, sibling to the existing `GroupMembershipEditor`): a combobox
  to add a position, an X to remove. Saves immediately, like group membership.
- Requires `role:manage` to edit the position→functional-role mapping; `role:assign` to
  assign positions to members.

### Functional roles screen (`/functional-roles`) — the rare, advanced surface

- For the handful of leaders with `role:manage`. Lists functional roles; detail shows the
  permission checklist (add/remove `Permission`s) and which positions map in.
- Intentionally lower-traffic: most troops never touch it. Positioned in settings/admin,
  not primary nav.

### Member view

A member's detail/edit page shows their **positions** (chips, like groups), never raw
functional roles or permissions. Self-view and permission gating per `members-screen.md`.

---

## Migration from the current `Role` model

The current code ships `Role`, `RolePermission`, `RoleMembership`,
`MemberRoleAssignment`, and `GroupRoleRule`, plus `/roles`, `/role-memberships`,
`/role-assignments` routers, `resolve_permissions`, and importer/provisioning hooks.
Because the product is pre-1.0 and these tables are only lightly seeded (just
`Administrators`), this is the cheap moment to split.

**Mechanical mapping:**

| Current | Becomes |
|---|---|
| `Role` (kind=functional group) | `FunctionalRole` |
| `Role` (kind=position) | `Position` |
| `Role.is_admin` | `FunctionalRole.is_admin` |
| `RolePermission` | `FunctionalRolePermission` |
| `RoleMembership` (group_role ← member_role) | `PositionFunctionalRole` (functional_role ← position) |
| `MemberRoleAssignment` | `MemberPositionAssignment` |
| `GroupRoleRule.role_id` | `GroupPositionRule.position_id` |

**Touch surface:** `app/models/role.py` (split), `app/models/group.py`
(`GroupRoleRule`→`GroupPositionRule`), `app/core/permissions.py` (flat resolver),
`app/core/groups.py` (position-based resolution), `app/core/provisioning.py`
(`ensure_administrators_role` → seed all positions/functional roles/mapping), the three
routers above, `app/schemas/role.py`, the TWH importer (maps TWH leadership → positions),
and a new Alembic migration with RLS wiring for every new table. Docs to update:
`session-permissions.md` (the `roles` field), `groups-screen.md` (role-rule wording),
`CLAUDE.md` (domain-model section).

Greenfield migration is acceptable (drop the old tables, create the new ones) since no
production data exists; the importer and provisioning are the only writers.

---

## Testing

- **Resolver:** member with one position → exactly that position's union of
  functional-role permissions; multiple positions → union; an `is_admin` functional role →
  full set; soft-deleted assignment/mapping/permission excluded at each hop.
- **Constraint enforcement:** no API path exists to attach a functional role or permission
  to a member (assert the routes 404/405); only positions are assignable.
- **Seed:** a freshly provisioned tenant has all default positions, functional roles, the
  mapping, and the founder holding the Administrator position → full permissions.
- **Group interplay:** a dynamic group with a `GroupPositionRule` resolves to exactly the
  members holding that position.
- **Cross-tenant isolation:** positions/functional roles/mappings never leak across
  tenants (RLS + `tenant_id` scoping), per existing `other_client` patterns.
- **ReBAC (when built):** `can_access_member` true for a parent→child pair and for an
  RBAC-permissioned actor; false for an unrelated member without `member:read`.

---

## Decisions

- **Permissions live only on functional roles** (positions hold none directly) for v1,
  with a forward-compat seam so a `PositionPermission` source can be added additively
  later — see [Forward-compat seam](#forward-compat-seam-direct-position-permissions).
- **Parents/guardians get read+write** to their own and their scouts' records via the
  ReBAC layer (self-service-equivalent scope, including medical and electronic permission)
  — see [the ReBAC axis](#the-third-axis-relationship-scoped-access-rebac--designed-here-built-later).

## Open questions

1. **Singleton positions.** Some positions are troop-unique (one Scoutmaster, one SPL).
   Do we enforce "at most one holder" (like patrols enforce one group), and is it
   troop-wide (Scoutmaster) vs per-patrol (Patrol Leader — one per patrol, not per troop)?
   The per-patrol case doesn't fit a simple flag; proposed: defer, treat as advisory.
2. **Position term/history.** Do we need start/end dates on `MemberPositionAssignment`
   (elections, annual turnover) beyond soft-delete + `created_at`? Affects whether the
   audit trail is sufficient or needs explicit terms.
3. **Reports & communications granularity.** `report:read` and the two `communication:*`
   permissions are coarse. Fine for now, or do reports need per-domain read scopes?
4. **TWH importer mapping.** TWH exports leadership/positions in its own vocabulary —
   we need the concrete crosswalk from TWH position names to seeded OpenTroop positions
   (and a fallback for unrecognized ones).
</content>
</invoke>
