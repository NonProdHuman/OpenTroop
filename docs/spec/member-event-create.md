# Add Member & Add Event — Create Flows Spec

**Status:** Draft
**Routes:** `/members/new` (create member) · `/events/new` (create event)
**Pillars:** Roster & Relationships (Pillar 1) · Event Management (Pillar 2)

---

## Overview

The Members and Events list screens each have an **Add** action in their page
header (`Add Member`, `Add Event`). Today those buttons render but are not wired to
anything — clicking them does nothing. This spec defines the create flows that back
them, mirroring the existing **New group** flow (`/groups/new`, `useCreateGroup`)
exactly in structure, navigation, and error handling so the three creation surfaces
behave identically.

The backend already exposes the endpoints — no API work is required:

- `POST /members/` (`MemberBase`) — gated by `member:write`.
- `POST /events/` (`EventBase`) — gated by `event:create`.

This is purely a frontend wiring task: two data hooks, two full-page create forms,
and two button `onClick` handlers.

---

## Actors and Permissions

| Permission | Capability |
|-----------|------------|
| `member:write` | Create a member via `/members/new` |
| `event:create` | Create an event via `/events/new` |

Permission enforcement lives on the backend. The frontend does not currently hide the
Add buttons by permission (consistent with the existing **New group** button), so this
spec does not change button visibility — a user lacking permission will receive a 403
from the API and see the form's error message.

---

## Navigation pattern (mirrors Groups)

```
/members        → List view (with detail sheet overlay)
/members/new    → Create form (full page)        ← NEW

/events         → List/calendar view (with detail sheet overlay)
/events/new     → Create form (full page)         ← NEW
```

- The **Add Member** / **Add Event** header buttons call `router.push("/members/new")`
  / `router.push("/events/new")`. This matches the **New group** button, which pushes
  `/groups/new`.
- Create is a **full-page route** (not a sheet/modal) so it works identically on mobile
  and desktop — the same rationale as `/groups/new`.
- On success the form navigates back to the list (`/members` or `/events`).
- A **Cancel** button (header and footer) returns to the list without saving.

---

## Add Member (`/members/new`)

### Form

The form reuses the field set and section layout of the existing
`/members/{id}/edit` page (`MemberEditForm`), minus the **Groups & Patrols** editor —
group membership requires a saved member id and is managed on the edit screen after the
member exists. Sections, in order:

1. **Identity** — first name\*, last name\*, middle name, suffix, nickname, date of
   birth, member type\* (scout/adult), status (active/inactive/alumni), BSA ID.
2. **Contact** — email, phone, address lines 1–2, city, state, postal code, country.
3. **Emergency Contacts** — contact 1/2 name + phone.
4. **Medical** — swim classification, swim eval date, health form A/B date, health form
   C date, allergies, dietary restrictions.
5. **Order of the Arrow** — `oa_member` toggle that reveals the OA detail fields (same
   as edit).
6. **Notes** — internal notes.

\* = required.

### Defaults

| Field | Default |
|-------|---------|
| `member_type` | `scout` |
| `membership_status` | `active` |
| `swim_classification` | `nonswimmer` |
| `country` | `US` |
| all other fields | empty |

### Validation

- **First name** and **last name** are required (non-empty after trim). If either is
  missing, show inline error `First name and last name are required.` and do not submit.
- Empty optional text fields are converted to `null` before sending (same `nullify`
  helper as the edit form).

### Submit

- Calls `useCreateMember()` → `POST /members/`.
- On success: navigate to `/members`. React Query invalidates `["members"]` so the new
  row appears.
- On error: show an inline error message. A 403 (no permission) and network failure both
  surface as a generic "could not save" message, consistent with the group form.

---

## Add Event (`/events/new`)

### Form

A full-page form with the core event fields. Sections, in order:

1. **Basics** — name\*, event type\* (select of active `EventType`s).
2. **When** — all-day toggle, scheduled start\*, scheduled end\*. Times use
   `datetime-local` inputs; when **all-day** is checked the inputs collapse to `date`.
3. **Where** — location (select of existing `Location`s, optional), location notes,
   departure location, return location, video conference URL.
4. **Sign-up & cost** — signup start date, signup deadline date, scout limit, adult
   limit, youth cost, adult cost.
5. **Details** — description, agenda.

\* = required.

### Event type and location options

- **Event type** options come from `useEventTypes()`, filtered to `is_active`. The select
  is required; the form cannot be submitted without one. If no active event types exist,
  show a hint linking the user to Settings (event types are seeded on tenant creation, so
  this is an edge case).
- **Location** options come from a new `useLocations()` hook (`GET /locations/`). Location
  is optional; a "— None —" option clears it. One-off spots use the free-text **location
  notes** field instead.

### Defaults

| Field | Default |
|-------|---------|
| `event_type_id` | first active event type (if any) |
| `scheduled_start` | next top-of-hour (local) |
| `scheduled_end` | one hour after start |
| `all_day` | `false` |
| all other fields | empty |

### Validation

- **Name**, **event type**, **scheduled start**, **scheduled end** are required.
- **Scheduled end must not be before scheduled start** — inline error if violated.
- Numeric fields (limits, costs) are coerced; empty → `null`. Costs are sent as strings
  (Decimal); limits as integers.

### Submit

- Calls `useCreateEvent()` → `POST /events/`.
- On success: navigate to `/events`. React Query invalidates `["events"]`.
- On error: inline error message (same pattern as the member/group forms).

---

## Data hooks

New hooks, following the `useCreateGroup` shape (mutation + `invalidateQueries`):

```ts
// src/hooks/use-members.ts
useCreateMember()  // POST /members/ → invalidates ["members"]

// src/hooks/use-events.ts
useCreateEvent()   // POST /events/  → invalidates ["events"]
useLocations()     // GET  /locations/ (query, for the event location picker)
```

---

## Out of scope

- Editing audiences, organizers, and participants at create time (managed after creation).
- Setting a member's group/patrol membership at create time (use the edit screen).
- Creating a new `Location` inline from the event form (pick from existing; manage
  locations elsewhere).
- Permission-aware hiding of the Add buttons (unchanged from current behavior).

---

## Testing

- Member create form: renders required-field validation; submitting with a valid name
  calls the create hook with the expected payload and navigates to `/members`.
- Event create form: renders; end-before-start validation blocks submit; a valid submit
  calls the create hook and navigates to `/events`.
- Both list pages: the Add button navigates to the corresponding `/new` route.
</content>
</invoke>
