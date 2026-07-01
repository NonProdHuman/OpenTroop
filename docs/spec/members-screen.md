# Members Screen Spec

**Status:** Draft
**Routes:** `/members` (list) · `/members/{id}` (detail) · `/members/{id}/edit` (edit)
**Pillar:** Roster & Relationships (Pillar 1)
**Related:** [`baseline-member-access.md`](baseline-member-access.md) — the "Basic" tier
below assumes every member has read access by default, which isn't true today; that spec
closes the gap

---

## Overview

The Members screen is the primary roster view for the troop. It is visible to every
authenticated member of the tenant. What a viewer can *see* and *do* depends on their
permission set; the layout adapts to those permissions without exposing the fact that
additional fields exist.

---

## Actors and Permission Tiers

Four permission tiers apply to this screen. A viewer's effective permissions come from
`resolve_permissions(member_id, session)` — the transitive role walk already implemented
in `app/core/permissions.py`.

| Tier | Permission(s) required | What it unlocks |
|------|----------------------|-----------------|
| **Basic** | any authenticated troop member (no special permission) | Roster list (name, patrol, type, primary role); own full record |
| **Contact** | `member:read_contact` | Email, phone, mailing address, emergency contacts for all members |
| **Medical** | `member:read_medical` | Swim classification, medical form dates, allergies, dietary restrictions for all members |
| **Edit** | `member:write` · `member:write_medical` · `member:delete` | Respective write capabilities (write_medical gates only the medical section) |

**Self-view exception:** A member can always see their own complete record — all fields,
all sections — regardless of which permissions they hold. This applies on both the list
and detail views. The frontend enforces this by comparing the viewed `member.id` against
the current user's resolved member ID for the tenant.

---

## Routes

```
/members              → List view
/members/{id}         → Detail view (read)
/members/{id}/edit    → Edit form
```

### Navigation pattern decision

The detail view is a **full-page route** (`/members/{id}`), not a slide-over panel,
drawer, or split-pane.

**Rationale:** A full-page route is identical on mobile web, desktop web, and native
mobile (which uses the same URL structure or maps it to a stack navigation push). A
split-pane only works on wide screens; a sheet/drawer requires coordinating open/close
state with the URL bar, complicating deep-linking and back-navigation. The full-page
approach minimizes the design delta between web and mobile.

As a future desktop enhancement, a Sheet component could intercept list-row clicks and
render the detail view in an overlay (the canonical `/members/{id}` route still exists
and is the fallback). This enhancement should not be built until mobile is underway and
the patterns are confirmed to be compatible.

---

## List View (`/members`)

### Default state

- Shows **active members only** by default (`membership_status = active`).
- Sorted by last name ascending.
- No search query; no type filter applied.

### Search

- A single text input searches across `first_name`, `last_name`, and `nickname` fields.
- Search is **case-insensitive prefix/substring match**.
- For tenants with rosters under ~500 members, filtering can run client-side against
  the full list fetched on mount. For larger rosters, the API must support a `?search=`
  query parameter — implement client-side first and add server-side when needed.
- The search input is persistent: navigating to a detail view and returning preserves
  the search state (store in URL query param `?q=`).

### Filters

Filters are surfaced as a compact filter bar below the search input.

| Filter | Options | Default | URL param |
|--------|---------|---------|-----------|
| Status | Active · Inactive · Alumni · All | Active | `?status=` |
| Type | All · Scouts · Adults | All | `?type=` |
| Patrol/Group | All · [list of PATROL groups] | All | `?group=` |

- Active filters are visually indicated (e.g. filled chip vs. outline chip).
- Filter state is stored in URL query params so links are shareable and back-navigation
  restores the filtered view.

### List item

Each row in the list displays:

```
[Avatar]  [Full name]          [Patrol name]
          [Primary role/pos]   [Type badge: Scout | Adult]
```

- **Avatar:** initials-based placeholder (first + last initial). Photo support is future work.
- **Full name:** `preferred_name ?? first_name` + `last_name` — use `nickname` as the
  display first name if set.
- **Patrol name:** the member's `PATROL`-type group name, if any. Blank if unassigned.
- **Primary role/position:** the member's most relevant role title. If they hold multiple
  roles, surface the highest-precedence one (positions over functional groups; use display
  order TBD — can fall back to alphabetical for now). Blank if no role assigned.
- **Type badge:** `Scout` or `Adult`. Small, low-contrast — secondary info.

**Inactive / alumni members** (when shown via status filter) appear with reduced opacity
or a muted color treatment to visually distinguish them from active members.

### Responsive behavior

On **narrow viewports (mobile):** single-column card layout. Each card is the full
list-item layout described above.

On **wide viewports (desktop):** a data table with columns: Name · Patrol · Role · Type.
The avatar moves into the Name column as a leading element. Status column added when the
status filter is set to "All" or "Alumni"/"Inactive".

The table/card toggle is driven purely by viewport width (Tailwind responsive prefix) —
no JavaScript detection needed.

### Empty states

| Condition | Message |
|-----------|---------|
| Roster has no members | "No members yet. Import from TroopWebHost or invite the first member." |
| Search returns nothing | "No members match '[query]'. Try a different name." |
| Filter combination returns nothing | "No members match the selected filters." |

---

## Detail View (`/members/{id}`)

A full-page view of a single member record. Content is conditionally rendered based on
the viewer's permission tier. Sections that the viewer has no access to are **not
rendered at all** — no "redacted" placeholder.

### Header (all tiers)

```
[Avatar — large]  [Display name]
                  [Type badge]  [Status badge]
                  [Patrol name]  [Primary role]
```

Status badge: shown only when `membership_status ≠ active` (Inactive / Alumni).

**Actions menu** (top-right, rendered per permission):

| Action | Requires | Notes |
|--------|----------|-------|
| Edit | `member:write` | Navigates to `/members/{id}/edit` |
| Send Invite | `member:write` + `member.user_id IS NULL` | Calls `POST /members/{id}/invite`; button disabled if already claimed |
| Mark Inactive | `member:write` + status is active | PATCH `membership_status → inactive` |
| Reactivate | `member:write` + status is inactive/alumni | PATCH `membership_status → active` |
| Delete | `member:delete` | Soft-delete (`is_deleted = true`). Requires confirmation dialog. |

### Section: Contact Info (requires `member:read_contact` or self)

| Field | Source |
|-------|--------|
| Email | `member.email` |
| Phone | `member.phone` |
| Address | `address_line1`, `address_line2`, `city`, `state`, `postal_code`, `country` |

### Section: Emergency Contacts (requires `member:read_contact` or self)

Two emergency contacts. For each: name, relationship, phone, email.

Fields: `emergency_contact_1_name`, `emergency_contact_1_relationship`,
`emergency_contact_1_phone`, `emergency_contact_1_email` (and `_2_` equivalents).

Render only contacts where the name field is non-empty. If both are empty, the section
is not shown.

### Section: BSA Info (all tiers — no PII)

| Field | Source | Notes |
|-------|--------|-------|
| BSA ID | `member.bsa_id` | Nullable; omit row if null |
| Member since | `member.created_at` | Formatted as month + year |
| Membership status | `member.membership_status` | Only shown if ≠ active |

### Section: Medical (requires `member:read_medical` or self)

| Field | Source | Notes |
|-------|--------|-------|
| Swim classification | `member.swim_classification` | BSA: Nonswimmer / Beginner / Swimmer |
| Swim eval date | `member.swim_date` | Nullable |
| Health form Part A/B | `member.medical_form_ab_date` | Nullable; shown as expiry date |
| Health form Part C | `member.medical_form_c_date` | Nullable |
| Allergies | `member.allergies` | Free text; nullable |
| Dietary restrictions | `member.dietary_restrictions` | Free text; nullable |

Medical form dates: display as "Expires [date]" with a visual warning if within 30 days
of expiry, and an error state if expired.

### Section: Order of the Arrow (all tiers — shown only if `member.oa_member = true`)

| Field | Source |
|-------|--------|
| Status | `oa_active` → Active / Inactive |
| Election date | `oa_election_date` |
| Call-out date | `oa_call_out_date` |
| Ordeal date | `oa_ordeal_date` |
| Brotherhood date | `oa_brotherhood_date` |
| Vigil date | `oa_vigil_date` |
| Vigil name | `oa_vigil_name` |
| Notes | `oa_notes` |

Only render date rows where the value is non-null.

### Section: Roles (all tiers)

List of the member's current active `MemberRoleAssignment` records. For each:
role name · assigned date. Soft-deleted assignments are not shown.

### Section: Family / Relationships (all tiers)

Resolved from `Member.outgoing_relationships` + `Member.incoming_relationships`.
For each relationship: the other member's display name (linked to their detail page)
and the relationship type expressed from this member's perspective:

| `relationship_type` | Displayed as (from this member's view) |
|---------------------|----------------------------------------|
| `parent_of` (outgoing) | Parent of [name] |
| `parent_of` (incoming) | Child of [name] |
| `guardian_of` (outgoing) | Guardian of [name] |
| `guardian_of` (incoming) | Ward of [name] |
| `sibling_of` | Sibling of [name] |
| `other` | Related to [name] |

Linked names navigate to the related member's detail page. If the viewer doesn't have
permission to view the related member (cross-tenant guard, future multi-troop support),
show the name without a link.

---

## Edit View (`/members/{id}/edit`)

Accessible to holders of `member:write`. Medical sub-section additionally requires
`member:write_medical`. A member can edit their own record regardless of held permissions.

The edit view is a **single scrollable form** divided into the same sections as the
detail view. This avoids a multi-step wizard (adds complexity) and a tabbed layout
(hides context).

### Editable fields by section

**Identity**

| Field | Input type | Constraints |
|-------|-----------|-------------|
| First name | Text | Required |
| Middle name | Text | Optional |
| Last name | Text | Required |
| Name suffix | Text | Optional (Jr., Sr., III, etc.) |
| Nickname / preferred name | Text | Optional |
| Date of birth | Date picker | Optional; cannot be future date |
| Member type | Select: Scout / Adult | Required |
| Membership status | Select: Active / Inactive / Alumni | Required |
| BSA ID | Text | Optional; validated as numeric; unique within tenant when set |

Group memberships (including patrol) are managed in the **Groups & Patrols** section below, not inline in Identity.

**Contact** (requires `member:write`)

| Field | Input type |
|-------|-----------|
| Email | Email input |
| Phone | Tel input |
| Address line 1 | Text |
| Address line 2 | Text |
| City | Text |
| State | Text (2-letter abbreviation) |
| Postal code | Text |
| Country | Text (default: US) |

**Emergency Contacts** (requires `member:write`)

Two identical contact blocks: name, relationship, phone, email.

**Medical** (requires `member:write_medical`)

| Field | Input type |
|-------|-----------|
| Swim classification | Select: Nonswimmer / Beginner / Swimmer |
| Swim eval date | Date picker |
| Health form Part A/B date | Date picker |
| Health form Part C date | Date picker |
| Allergies | Textarea |
| Dietary restrictions | Textarea |

**Groups & Patrols** (requires `member:write`)

Displays the member's current group memberships as tag bubbles and provides a combobox
to add them to additional groups. This is the primary surface for managing group membership
from the member's perspective; the Groups screen provides the inverse view (members of a
group).

*Tag bubble appearance:*

Each bubble shows a small type icon + group name. The bubble's accent color comes from
`group.color` (hex). When `group.color` is null, the type determines the fallback:

| Group type | Icon | Fallback color | X button |
|---|---|---|---|
| `patrol` | shield | amber | Yes — removes from this patrol |
| `manual` | users | blue | Yes — removes `GroupMember` row |
| `dynamic` | bolt | violet | **No** — read-only; membership is rule-driven |
| `is_system = true` | lock | gray | **No** — read-only; system-managed |

Dynamic group bubbles show a tooltip on hover: *"Auto-assigned via role rule."*
System group bubbles show: *"System group — membership is managed automatically."*

*Adding a group:*

A combobox dropdown lists groups the member does not currently belong to. Dynamic groups
and system groups are excluded from the add list — their membership is not manually
managed. Patrol groups appear in the add list alongside manual groups.

Patrol single-selection: a member belongs to at most one `PATROL` group. If the member
is already in a patrol and a new patrol is selected from the dropdown, the old patrol
bubble is replaced (the backend `POST /groups/{id}/members` handles the swap atomically
via `_clear_patrol_membership`). The UI shows the old patrol bubble as "pending removal"
(strikethrough or muted) until save confirms.

*Persistence:*

Group membership changes are **saved immediately** (not deferred to the form save button)
using optimistic updates:
- Add: `POST /groups/{group_id}/members` with `{member_id}`
- Remove: `DELETE /groups/{group_id}/members/{member_id}`

Saving immediately (rather than batching with the member PATCH) keeps the mental model
simple — the bubbles always reflect current server state, and there is no "unsaved group
changes" edge case to handle.

**Order of the Arrow** (requires `member:write`; section is hidden if `oa_member = false`)

- `oa_member` toggle: when turned on, reveals the rest of the OA section.
- `oa_active` toggle.
- Date pickers for each milestone date.
- Text input for vigil name.
- Textarea for notes.

### Form behavior

- **Save:** `PATCH /members/{id}` with the changed fields. On success, navigate back
  to `/members` (the list). The detail sheet can be re-opened from there.
- **Cancel:** navigate back to `/members` without saving. No confirmation dialog unless
  the form is dirty (any field modified).
- **Validation:** client-side validation before submit; surface field-level errors from
  the API response inline.
- **Group membership changes:** saved immediately on add/remove (see Groups & Patrols
  section above), independent of the form save button. No group membership state is
  held in the form.

---

## Open Questions

1. ~~**Patrol assignment via edit form:**~~ **Resolved.** The backend's
   `POST /groups/{id}/members` already handles atomic patrol swaps via
   `_clear_patrol_membership`. Group membership changes are saved immediately (not
   batched with the member PATCH). No new backend endpoint needed.

2. **Photo/avatar:** Placeholder-only for now. When implemented, photos likely come from
   Clerk profile photos (for claimed accounts) or a separate upload. Leave the avatar
   component interface-ready (accepts `src` prop, falls back to initials).

3. **Search pagination:** At what roster size does client-side search become a problem?
   Suggest implementing server-side search at the API layer now (even if the frontend
   doesn't use it yet), so the mobile client can use it from the start.

4. **Multiple roles display:** When a member holds 3+ roles, the list-item role display
   needs a truncation/tooltip strategy. Punted to implementation.

5. **Export:** Leaders will want to export the filtered roster to CSV. Treat as a
   follow-on feature; the filter/search URL params make the scope clear.
