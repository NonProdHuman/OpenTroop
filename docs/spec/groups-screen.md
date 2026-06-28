# Groups Screen Spec

**Status:** Draft
**Routes:** `/groups` (list + detail sheet) · `/groups/new` (create) · `/groups/{id}/edit` (edit)
**Pillar:** Roster & Relationships (Pillar 1)

---

## Overview

The Groups screen is the primary surface for managing the troop's groups and patrols.
Every group is a first-class object: patrols, PLC, SPL team, OA chapter — all managed
here. The screen mirrors the Members screen in layout and interaction pattern.

---

## Actors and Permissions

| Permission | Capability |
|-----------|------------|
| `member:read` (any authenticated member) | View group list and group detail |
| `member:write` | Create, edit, and delete groups; manage group membership from the group side |

---

## Routes

```
/groups            → List view (with detail sheet overlay)
/groups/new        → Create form (full page)
/groups/{id}/edit  → Edit form (full page)
```

**Navigation pattern:** Identical to the Members screen.
- The list and detail sheet share `/groups` — clicking a row opens the detail sheet
  without navigating away. The sheet closes when the user clicks elsewhere or presses
  Escape.
- Create and edit are **full-page routes** (`/groups/new`, `/groups/{id}/edit`) so they
  work identically on mobile and desktop.

---

## List View (`/groups`)

### Default state

- All non-deleted groups, sorted alphabetically.
- System groups shown below non-system groups (separated by a section label).
- No filter applied by default.

### Filter / search

A search input filters by group name (client-side substring match). No other filters
needed at this stage.

### List columns (table on desktop, cards on mobile)

| Column | Content |
|--------|---------|
| Color swatch + Name | `group.color` dot + `group.name` |
| Type badge | Patrol · Manual · Dynamic |
| Members | Count of resolved members (from `GET /groups/{id}/members`) |
| System indicator | Lock icon if `is_system = true` |

Member counts are fetched lazily — show a "—" placeholder until the count resolves.
Use the cached `group-members` query data if already in cache (the member edit page may
have pre-fetched it).

### Empty state

```
No groups yet.
Groups organize your roster for events, messaging, and patrol assignments.
[New group →]
```

### Actions

- **New group** button (top-right of page header) — navigates to `/groups/new`.
- Clicking any row opens the **detail sheet** (right side panel).

---

## Detail Sheet (right panel, overlays `/groups`)

Triggered by clicking a list row. Dismissed by clicking outside or pressing Escape.

### Header

```
[Color swatch]  [Group name]
                [Type badge]  [System badge if applicable]
```

### Actions (top-right of sheet, rendered per permission)

| Action | Requires | Notes |
|--------|----------|-------|
| Edit | `member:write` | Navigates to `/groups/{id}/edit` |
| Delete | `member:write` + `is_system = false` | Soft-delete. Requires confirmation. Disabled with tooltip if `is_system = true`. |

### Section: Members

Resolved member list for this group. Each entry: member avatar (initials) + display name
+ member type badge. Clicking a member name navigates to `/members/{id}`.

If the group has no members: "No members yet."

For **dynamic** groups, show a note below the member list:
*"Membership is automatic — driven by role rules below."*

### Section: Position Rules (dynamic groups only)

Shown only when `group_type = "dynamic"`. Lists each `GroupPositionRule`: the position
name that triggers membership. Read-only in the detail sheet; managed on the edit page.

### Section: Description

Show `group.description` if non-null. Otherwise omit the section entirely.

---

## Create View (`/groups/new`)

A full-page form for creating a new group. Navigated to from the "New group" button.
On save, navigates to `/groups`. On cancel, navigates to `/groups`.

### Fields

| Field | Input | Constraints |
|-------|-------|-------------|
| Name | Text | Required. Must be unique within tenant (backend enforces with 409). |
| Type | Select: Patrol · Manual | Required. Dynamic is excluded — dynamic groups are created automatically by the system via role rules, not by users. |
| Color | Color swatch picker | Optional. 8 preset swatches + a free-text hex input for custom colors. |
| Description | Textarea | Optional. |

### Color picker

8 preset swatches are shown as clickable circles. A small text input below the swatches
accepts a custom hex value (e.g. `#4CAF50`). The selected color updates the swatch ring
highlight. Default: first preset (amber, `#F59E0B`) for patrols; blue (`#3B82F6`) for
manual.

### Save behavior

`POST /groups/` with `{ name, group_type, color, description }`. On 201, invalidate
`["groups"]` and navigate to `/groups`. On 409 (duplicate name), show inline error:
*"A group with this name already exists."* On other errors, show a generic error banner.

---

## Edit View (`/groups/{id}/edit`)

Accessible to holders of `member:write`. Navigated to from the detail sheet "Edit"
action.

### Editable fields

Same fields as Create (Name, Type, Color, Description). All pre-populated from the
existing group record.

**Restrictions:**
- `is_system = true` groups: name and type are read-only (shown as plain text, not
  inputs). Color and description remain editable.
- `group_type = "dynamic"`: type is read-only (changing a dynamic group to manual would
  orphan its role rules).

### Section: Members

Lists current members (same as the detail sheet). From the edit page, members can be
**added** and **removed** directly:

- **Remove:** an X button on each member row. For dynamic groups, the X is hidden
  (membership is rule-driven). For system groups, the X is hidden.
- **Add:** a combobox (search by name) to add any troop member to this group.
  Adding a member to a patrol group triggers the backend's atomic patrol swap
  (`_clear_patrol_membership`) — the member is automatically removed from their
  previous patrol if they had one.

Changes save immediately (not batched with the form save button), same pattern as
the `GroupMembershipEditor` on the member edit page.

### Section: Position Rules (dynamic groups only)

Shown only for `group_type = "dynamic"`. Lists current `GroupPositionRule` rows. Leaders
can add a rule (select a position from a dropdown) or remove an existing rule. Changes
save immediately.

### Save behavior

`PATCH /groups/{id}` with changed fields. On success, navigate to `/groups`. On 409
(duplicate name), show inline error. On other errors, show a generic error banner.

### Cancel behavior

Navigate to `/groups` without saving. No confirmation dialog unless the form is dirty.

---

## Constraints and edge cases

| Case | Behavior |
|------|----------|
| Delete last non-system group | Allowed — the tenant can have zero groups |
| Delete a group with members | Soft-delete the group; `GroupMember` rows are orphaned but not deleted (they become unreachable). A future cleanup job can reap them. |
| Rename to an existing name | Backend returns 409; show inline field error |
| Patrol with members — user changes type to manual | Allowed (patrol single-membership constraint is type-specific; changing type releases it). Show a warning: *"Changing a patrol to a manual group removes the single-membership constraint."* |
| System group edit attempted | Edit button visible but name/type fields are read-only; a banner explains: *"System groups are managed by OpenTroop. Name and type cannot be changed."* |

---

## Open Questions

1. **Member count performance:** Fetching member counts for every group in the list
   requires N parallel requests. If the tenant has many groups, this is expensive.
   Consider a `GET /groups/?include_member_count=true` API enhancement that returns
   counts in a single query. Implement N-parallel for now; add the API param when it
   becomes a performance issue.

2. **Dynamic group creation:** Who creates dynamic groups and how? Currently they are
   implied by role rules but there is no UI path to create a `dynamic`-type group.
   Likely a platform/admin-only action. Deferred — document when role rule management
   is built.

3. **Group ordering:** Alpha sort is the default, but troop leaders may want to reorder
   patrols (e.g., show Eagle Patrol first). Drag-to-reorder is a future enhancement.
