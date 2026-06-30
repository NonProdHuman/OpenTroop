# Event Edit Spec

**Status:** Draft
**Routes:** `/events` (list/calendar) · detail Sheet (overlay) · `/events/{id}/edit` (edit)
**Pillar:** Event Management (Phase 1)

---

## Overview

Events can be created (`/events/new`) and viewed (read-only `EventDetailSheet` overlay),
but there is no way to **edit** an existing event and no leader-facing way to manage
RSVPs on behalf of other members. The self-service RSVP panel (`event-rsvp-panel.tsx`)
only covers the current member's household and explicitly defers leader-side attendee
management to "the event edit page."

This spec defines that edit page: a full-page route reached from an **Edit** button on
the event detail Sheet (mirroring the member detail Sheet → `/members/{id}/edit`
pattern), organized as two tabs:

- **Details** — every editable property of the event, plus visibility **audiences** and
  **organizers**.
- **RSVP** — a leader grid to set RSVP / driver / seatbelts / comment for each member who
  can see the event.

No backend changes are required; every endpoint already exists.

---

## Permissions

The whole page is gated on **`event:write`** (`Permission.EVENT_WRITE`). The Edit button on
the detail Sheet is only rendered for callers with `event:write`. Direct navigation by a
user lacking the permission surfaces a "You don't have permission to edit events." message
(API returns 403, mirroring the create page's error mapping).

A caller with `event:write` is an **event manager**: the backend's
`_require_can_act_for` allows managers to set RSVP fields for **any** member and bypasses
the sign-up window. This is what makes the RSVP admin tab possible with the existing
participant endpoints.

---

## Routes & navigation

```
/events              → list / calendar (existing)
(detail Sheet)       → read-only overlay opened from a row/calendar cell (existing)
/events/{id}/edit    → edit form (NEW)
```

The detail Sheet gains a **Pencil "Edit"** button in its header that closes the Sheet and
`router.push(\`/events/${id}/edit\`)`, exactly like `member-detail-sheet.tsx`. The edit
page loads the event via `useEvent(id)` with a "Loading…" guard, then renders the tabbed
form seeded from the loaded data.

---

## Tab 1 — Details

Reuses the shared field components extracted from the create page into
`events/event-form.tsx` (`EventFormFields`, `FormState`, `toFormState`, `toApiPayload`,
date helpers). The edit page seeds `FormState` from the event and saves via
`useUpdateEvent()` → `PATCH /events/{id}` (`EventUpdate`).

### Editable scalar fields (saved with the **Save** button)

Carried over from create:

- **Basics:** `name`, `event_type_id`
- **When:** `all_day`, `scheduled_start`, `scheduled_end` (datetime-local for timed
  events, date for all-day; converted to UTC instants via `toUtcInstant`)
- **Where:** `location_id` (Select from `useLocations()`, or "— None —"),
  `location_notes` (free text), `departure_location`, `return_location`,
  `video_conference_url`
- **Sign-up & cost:** `signup_start`, `signup_deadline`, `signup_limit_scouts`,
  `signup_limit_adults`, `cost_youth`, `cost_adult`
- **Details:** `description`, `agenda`

New on the edit page (not on create):

- **Activity:** `camping_nights` (int), `community_service_hours`, `conservation_hours`,
  `hiking_miles`, `backpacking_miles`, `paddling_miles`, `cycling_miles`, `water_hours`
  (all Decimal-as-string, nullable). Useful for logging metrics after an event happens.

Out of scope this pass: `tour_permit_submitted`, `attendance_taken`, `linked_event_id`.

### Location: list-or-free-text

Location is chosen from the tenant's saved `Location` list (`location_id` Select), **or**
left as a one-off via the free-text `location_notes`. Both may be set. A dedicated
location-management page is a separate, later effort; this page only consumes the
existing list.

### Audiences (visibility) — immediate-persist sub-resource

Below the scalar form, an **Audiences** editor lists the event's audience groups and lets
a manager add/remove them. This mirrors the member edit page's `GroupMembershipEditor`:
changes **persist immediately** via their own mutations, independent of the Save button.

- Empty audience set ⇒ event is **troop-wide** (visible to everyone with `event:read`).
- Adding the first group scopes visibility to that group; removing the last returns the
  event to troop-wide.
- Backed by `GET/POST /events/{id}/audiences` and `DELETE /events/{id}/audiences/{group_id}`.
  Group list comes from `useGroups()`.

### Organizers — immediate-persist sub-resource

An **Organizers** editor lets a manager choose one or more members as event organizers,
add/remove persisting immediately. Backed by `GET/POST /events/{id}/organizers` and
`DELETE /events/{id}/organizers/{member_id}`. Member list comes from `useMembers()`.

---

## Tab 2 — RSVP (leader admin)

A grid for managing RSVP on behalf of members, distinct from the self-service household
panel. Component: `events/[id]/edit/event-rsvp-admin.tsx`.

### Roster (who appears)

The roster is **audience-scoped** — the members who can actually see the event:

- If the event has **no audiences** → all **active** members (`useMembers()` filtered to
  `membership_status === "active"` and not deleted) — i.e. the troop-wide audience.
- If the event has audiences → the **union** of those groups' resolved members
  (`useGroupMembers(groupId)` per audience group, deduped by `member.id`).

The roster is **active-members-only** and offers:

- **Search** by name.
- **Filters:** member type (All / Scouts / Adults) and a **Drivers-only** toggle
  (driver state comes from the participant row).
- **Sort:** Name, Patrol, or RSVP (RSVP order: Going → Maybe → No response → Declined;
  all sorts fall back to name). Each row shows the member's patrol (from
  `usePatrolMemberships()`).

### Per-member controls

Each row exposes, persisting on change/blur via `useAddParticipant` (POST when no
participant row exists) / `useUpdateParticipant` (PATCH otherwise) — the same
local-draft-then-persist approach as `event-rsvp-panel.tsx`:

- **RSVP:** **Going / Declined / Clear** buttons (`going`, `declined`, and Clear →
  `no_response`). Per product decision, `maybe` is not offered here.
- **Driver** toggle (adults only, matching the self-service panel).
- **Seatbelts** = `seat_count` number input (1–15), shown when Driver is on.
- **Comment** text input (`comment`).

Setting RSVP through this tab relies on the manager bypass: any member's row can be set,
and the sign-up window is not enforced for managers.

Electronic permission slips are **not** handled here — that flow is guardian-only and
lives in the self-service panel (`/permission` endpoint has no manager bypass).

---

## Data layer (frontend)

New hooks in `apps/web/src/hooks/use-events.ts` (mirroring the members hooks):

- `useEvent(id)` — `GET /events/{id}`, key `[tenantId, "events", id]`.
- `useUpdateEvent()` — `PATCH /events/{id}`; on success `setQueryData([tenant,"events",id])`
  and invalidate `[tenant,"events"]`.
- `useEventAudiences(eventId)`, `useAddEventAudience(eventId)`, `useRemoveEventAudience(eventId)`.
- `useEventOrganizers(eventId)`, `useAddEventOrganizer(eventId)`, `useRemoveEventOrganizer(eventId)`.

New types in `apps/web/src/types/api.ts`: `EventAudience`, `EventOrganizer`.

Reused: `useEventTypes`, `useLocations`, `useEventParticipants`, `useAddParticipant`,
`useUpdateParticipant`, `useGroups`, `useGroupMembers`, `useMembers`, `usePermissions`.

---

## Edge cases

- **Hidden event 404:** `GET /events/{id}` 404s an event the caller can't see, but
  managers (`event:write`) bypass visibility, so the edit page always loads for them.
- **No active event types:** the type Select shows a "Manage types in Settings" hint
  (same as create).
- **All-day toggling:** normalizes start/end to date-only midnight, reusing the create
  page's `toggleAllDay` logic.
- **Cancel discards scalar edits** but audience/organizer/RSVP changes have already
  persisted (consistent with how the member editor's group/position/relationship editors
  behave).

---

## Verification

- `pnpm --filter web exec tsc --noEmit` and `eslint src` clean.
- Vitest: edit page loads an event and PATCHes changed scalar fields; RSVP admin resolves
  the audience-scoped roster and fires participant POST/PATCH with the target `member_id`
  for Going/Declined/Clear, driver, seat_count, and comment.
- Manual: open an event → Edit, change fields across both tabs, reload to confirm
  persistence; confirm a non-`event:write` user can't reach Edit.
