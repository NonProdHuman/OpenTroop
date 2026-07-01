# Event RSVP & Parent Permission Workflow — Spec

**Status:** Draft
**Pillar:** Event Management (Pillar 2)
**Routes (frontend):** `/events/{id}` (RSVP surface) · `/members/{id}/edit` (relationship editor)
**Depends on:** `MemberRelationship` (backend CRUD exists), `EventType`, `EventParticipant`,
event visibility (`app/core/event_visibility.py`)
**Related:** [`baseline-member-access.md`](baseline-member-access.md) resolves the
"members still can't `GET /events`" gap noted below

---

## Overview

This feature lets members RSVP to events, lets parents/guardians act on behalf of
their family, lets adults sign up to drive (independently of attending), and captures
**electronic parental permission** for scouts on event types that require it.

The data model already carries most of the needed fields on `EventParticipant`
(`rsvp_status`, `driver`, `seat_count`, `guest_count`, `comment`, and the
`electronic_permission_*` set) and on `EventType` (`allow_signups`,
`require_permission_slip`). This spec defines the **behavior, authorization, and
state machine** around those fields, plus the handful of net-new fields, and the
**prerequisite relationship-building UI** without which family RSVP cannot function.

The goal is an **official digital record**: a parent's permission acknowledgement is
legally meaningful and is bound to their strongly-authenticated (Clerk) identity. A
leader cannot record permission on a parent's behalf. (The broader legal framing is
out of scope; this matches how TroopWebHost operates.)

---

## Event-type capability flags

`EventType` flags gate the whole workflow. Their meaning, including two new flags:

| Flag | Meaning |
|------|---------|
| `allow_signups` | **This is the "requires RSVP" switch.** `false` ⇒ the event is informational (e.g. a Meeting): location + time only, no RSVP UI, no participants, no permission slips. `true` ⇒ members RSVP. |
| `require_permission_slip` | Only meaningful when `allow_signups=true`. `true` ⇒ scouts who are *going* need a signed parental permission. Ignored when `allow_signups=false`. |
| `allow_guests` *(new)* | `true` ⇒ the RSVP form exposes a **guest count** field for people not modeled in the roster (e.g. a BBQ where grandparents attend). `false` ⇒ guest count hidden/forced to 0. |

Validation: setting `require_permission_slip=true` while `allow_signups=false` is
rejected (or silently coerced — **decision: reject** with a 422 on event-type
create/update, since the combination is nonsensical).

---

## Data model changes

### `EventParticipant` (new fields)

| Field | Type | Notes |
|-------|------|-------|
| `drives_to` | `bool` default `false` | Informational: driver covers the outbound leg. Independent of `driver` only in UI; persisted only when `driver=true`. |
| `drives_from` | `bool` default `false` | Informational: driver covers the return leg. |
| `permission_message_snapshot` | `Text` nullable | The **exact tenant permission text** the parent agreed to, captured at sign time. Drives the "show the language they signed under" requirement and the future PDF. Null until permission is given. |

`drives_to` / `drives_from` are purely informational in v1 (carpool coordination).
Capacity/seat-allocation math is explicitly **not** on the roadmap, but storing the
direction now keeps that door open.

Existing fields reused as-is: `rsvp_status` (the attending answer), `driver`,
`seat_count` (seatbelts), `guest_count`, `comment` (the per-RSVP note),
`electronic_permission`, `electronic_permission_at`, `electronic_permission_by_id`,
`electronic_permission_signature`.

### `Tenant` (new field)

| Field | Type | Notes |
|-------|------|-------|
| `permission_message` | `Text` nullable | The troop's customizable permission-slip language, shown before a parent clicks "I Agree". Static text (no merge fields in v1). Null ⇒ a built-in BSA default is shown (default text deferred; ship nullable, fall back to a constant). |

> **Note:** `Tenant` is `PlatformBase`. A single `permission_message` column is the
> minimal change. If tenant-level settings proliferate later, migrate to a dedicated
> `TenantSettings` row — out of scope here.

### Migration

New columns on `event_participants` and `event_types` (both `TrackedBase` — RLS
already enabled, no new tables) and `tenants`. One Alembic autogenerate revision.

---

## RSVP form (per event type)

What the member sees on `/events/{id}` when `allow_signups=true`:

### Scout RSVP
- **Attending?** — `going` / `declined` / unknown (`no_response`). (`maybe` exists in
  the enum but is **not surfaced** for this flow.)
- **Note** — free text → `comment`.
- If event type `require_permission_slip` and status is `going` ⇒ a **permission slip
  is pending** until a parent/guardian signs (see state machine).

### Adult RSVP
- **Attending?** — `going` / `declined` / unknown.
- **Driver?** — checkbox, **independent of attending** (an adult may decline yet drive).
- If **Driver**: **To / From** (both independently selectable → `drives_to`,
  `drives_from`) and **seatbelts** (integer → `seat_count`).
- **Note** — free text → `comment`.

### Guests
- Shown only when event type `allow_guests=true`: **guest count** (integer →
  `guest_count`) for non-roster attendees.

A participant row is created **on demand** the first time a member (or their parent)
RSVPs — rows are not pre-seeded from audiences.

---

## Authorization — who may RSVP for whom

RSVP/permission actions resolve through the `MemberRelationship` graph. "Family" is
**derived**, not stored as extra edge types:

- A member may always act for **themselves** (their claimed `User` → `Member`).
- A **parent/guardian** may act for any member in their **household**, where household
  is computed from `parent_of` / `guardian_of` edges:
  - **Children/wards:** members I have a `parent_of`/`guardian_of` edge to.
  - **Co-parents (other adults):** any adult who shares a child with me is mutually
    authorized (the "two adults sharing a child" rule — covers spouses without needing
    a `spouse_of` type).
  - **Siblings:** any two scouts who share a parent are siblings (derived).
- **Boundary — household, not transitive.** The closure stops at *shared children*. If
  Parent A and Parent B share child X, and Parent B has child Y with a different
  co-parent C, then **C is not in A's family** and A cannot act for C or Y. One hop
  through a shared child; no chaining through a child's *other* parents.
- Authorization keys off the **relationship**, not account-claim status: any Member
  with the right edge can be **acted for** even if that Member is unclaimed/imported.
  (The *acting* parent must be a claimed user to be authenticated, but the *target*
  need not be claimed.)

A helper — e.g. `family_member_ids(member_id, session)` in `app/core/relationships.py`
(mirroring `resolve_group_members`) — returns the `frozenset[member_id]` an actor may
RSVP for. The participants endpoints enforce it.

### Parent override of a child's RSVP
A parent **may override** a child's existing RSVP (e.g. scout said `going`, parent sets
`declined`). The UI must **show the child's current RSVP** before the parent changes it
(guard against accidental override). Persistence is last-write-wins; no precedence rule.

### Endpoint enforcement (replaces today's bare `event:read` gate)
- The participant **write** endpoints (`POST`/`PATCH`/`DELETE .../participants`, and
  `POST .../permission`) **drop the `event:read` permission gate** and instead require
  only tenant membership (`CurrentMemberDep`). Rationale: a plain scout/parent holds no
  RBAC permissions (permissions come from positions), so an `event:read` gate would lock
  them out of RSVPing for themselves. Authorization is then the family/manager check
  below. The **read** views (`GET .../participants`, `GET .../counts`) remain `event:read`
  management surfaces.
  > Broader gap noted: members still can't `GET /events` (also `event:read`-gated). A
  > baseline member-read capability is a separate concern, out of scope here.
- `POST`/`PATCH`/`DELETE .../participants`: caller may act only for
  `member_id ∈ family_member_ids(caller)` (which includes `caller`).
- **Event managers** (`event:write`) bypass the family scope — they administer any
  participant (consistent with the existing visibility-bypass pattern).
- `POST .../participants/{member_id}/permission`: gated to a **direct parent/guardian**
  (`is_guardian_of`), with **no** manager bypass — a leader cannot sign for a parent.

### Implementation notes (backend, done)
- `permission_status` (`PermissionSlipStatus`: `not_required`/`pending`/`granted`) is a
  **derived, non-persisted** field on the participant read, computed per request in
  `app/core/permission_slip.py` from the event type, RSVP, and current tenant message.
- Counts: `GET /events/{id}/counts` → `{scouts, adults, drivers, guests}`.
- Tenant message: `GET`/`PATCH /tenant/settings` (`app/routers/tenant_settings.py`);
  read gated `event:read`, write gated `role:manage`. Default lives in
  `permission_slip.DEFAULT_PERMISSION_MESSAGE` (placeholder until real BSA text).

---

## Permission-slip state machine (scouts only, `require_permission_slip` types)

States are derived from existing/new fields, not a stored enum:

1. **Not required** — scout not `going`, or event type doesn't require a slip.
2. **Pending** — scout `rsvp_status=going`, no permission recorded
   (`electronic_permission=false`). This is the actionable state the parent resolves.
3. **Granted** — a parent/guardian has acknowledged. Records:
   `electronic_permission=true`, `electronic_permission_at` (now),
   `electronic_permission_by_id` (the acting parent's Member),
   `electronic_permission_signature` (typed name / Clerk identity marker),
   `permission_message_snapshot` (the tenant text at sign time).

### Flow
1. Scout or parent RSVPs the scout as `going`.
2. **Pending.** If the parent did the RSVP, they're prompted to give permission
   **immediately** after. If the scout did it, the parent acts later (via a
   notification — *notifications are TBD/out of scope* — or by opening the event and
   clicking **"Give permission"** next to the child's RSVP).
3. Parent is shown the **tenant permission language**, then clicks **"I Agree"**.
4. Acknowledgement is recorded (who + when + the snapshotted language) → **Granted**.

### Validity & revival rules
- A granted permission is **only valid/displayed while the child is `going`**. If the
  child is `declined`/`no_response`, the slip is not shown or honored.
- **Revival:** `going → declined → going` **revives** the original permission — the
  parent need not re-sign, *provided the snapshotted language still matches the current
  tenant message*. If the tenant edited `permission_message` in the meantime, the slip
  returns to **Pending** and must be re-signed under the new text.
- **Language is captured at sign time** (`permission_message_snapshot`). Editing the
  tenant message never rewrites already-signed slips — they retain the wording the
  parent actually agreed to (legal record). The future permission-slip PDF renders from
  the snapshot.

### Who can grant
Only a parent/guardian in the scout's household (per authorization rules). **Leaders
cannot** record permission on a parent's behalf — there is no paper-slip-entry path.
This is deliberate: the record's value is the authenticated parent acknowledgement.

---

## Participant counts

Displayed on the event for managers:

- **Scouts** = scouts with `rsvp_status=going`.
- **Adults** = adults with `rsvp_status=going`.
- **Drivers** = members with `driver=true` **regardless of attending status**. An
  attending adult driver counts in **both** Adults and Drivers; a non-attending driver
  (`declined`/`no_response`, `driver=true`) counts in **Drivers only**.
- **Guests** = sum of `guest_count` (only relevant on `allow_guests` types) — shown
  separately, not folded into Scouts/Adults.
- `maybe` does not contribute to any headcount (and isn't surfaced in this flow).

---

## Signup window enforcement

The event's existing `signup_start` / `signup_deadline`:

- If set, RSVP create/update by a **regular member/parent** is **blocked** outside the
  window (422/409). Before `signup_start` or after `signup_deadline` ⇒ rejected.
- If a field is **null**, that side of the window is **unrestricted**.
- **Event managers** (`event:write`) may RSVP/edit participants regardless of the window
  (same bypass as family scope).

---

## Relationship-building UI (prerequisite)

Family RSVP is unusable until troops can build the family graph in-app. Backend CRUD
exists at `/relationships`; there is **no app UI and no `useRelationships` hook** today.
TWH import is currently the only way relationships get created.

### Scope for this feature
- **Surface:** the existing **member detail / edit screen** (`/members/{id}/edit`) gets
  a **Family / Relationships** section.
- **Capabilities:** add and remove relationships from this member to another member,
  choosing the relationship type (`parent_of`, `guardian_of`, `sibling_of`, `other`)
  with the directional convention from the model (adult is `from_member` for
  parent/guardian; siblings stored lower-UUID-first).
- **Actor:** a **leader** (`member:write`) manages these. Parent self-service editing of
  their own family links is **out of scope for v1**.
- **Hook:** new `useRelationships(memberId)` / `useCreateRelationship` /
  `useDeleteRelationship` in `apps/web/src/hooks/use-relationships.ts`, following the
  `use-groups` mutation+invalidate shape.

---

## Out of scope

- **Notifications** of any kind (the "parent gets prompted" channel) — TBD, separate.
- **Permission-slip PDF generation** — planned (drivers carry it on trips); renders from
  `permission_message_snapshot` later.
- **Time-slot / shift sign-ups** — TBD, separate feature.
- **Driver capacity / seat-allocation math** — direction is stored but unused.
- **Parent self-service** management of their own family links.
- **Merge fields** in the permission message (static text only in v1).
- **A default BSA permission message** — `permission_message` ships nullable with a
  placeholder constant; real default text added later.

---

## Testing

- **Event-type flags:** `require_permission_slip=true` with `allow_signups=false` is
  rejected. `allow_guests` toggles guest-count exposure.
- **Authorization:** a parent can RSVP for a child, a ward, a co-parent, and a sibling
  set; **cannot** reach a co-parent's *other* household (the A/B/C boundary case). A
  scout can act only for self. A manager bypasses scope.
- **Override:** parent overrides a scout's `going` to `declined`; child's prior RSVP is
  readable first.
- **Driver:** non-attending driver row counts in Drivers but not Adults; attending
  adult driver counts in both; `drives_to`/`drives_from`/`seat_count` persist.
- **Permission state machine:** pending on scout `going`; granted records who/when/
  snapshot; declining hides the slip; `going→declined→going` **revives** without
  re-sign; editing the tenant message forces re-sign and a new snapshot.
- **Snapshot integrity:** editing `permission_message` does not mutate already-signed
  participants' `permission_message_snapshot`.
- **Signup window:** member blocked before `signup_start` / after `signup_deadline`;
  unrestricted when null; manager bypasses.
- **Counts:** scouts/adults/drivers/guests computed per the rules above.
- **Relationship UI hook:** create/delete invalidate and refetch the member's relationships.
