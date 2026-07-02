# Baseline Member Access Spec

**Status:** Implemented (see GH-140 for the closing audit)
**Pillar:** Roster & Relationships (Pillar 1) — RBAC extension
**Related:** [`roles-rbac.md`](roles-rbac.md) · [`members-screen.md`](members-screen.md) · [`event-rsvp-permission.md`](event-rsvp-permission.md) · [`position-history.md`](position-history.md)
**Resolves:** the gap `event-rsvp-permission.md` explicitly deferred ("Broader gap noted:
members still can't `GET /events`... A baseline member-read capability is a separate
concern, out of scope here") and brings `members-screen.md`'s "Basic tier: any
authenticated troop member (no special permission)" in line with what the API actually
enforces today (it doesn't — `GET /members` and `GET /events` both hard-require
`member:read` / `event:read`, which nothing grants by default). Also closes the write-side
counterpart: a plain member/parent can't edit their own contact/medical info without
`member:write` (event RSVP self-service already works — see
[Self & family write access](#self--family-write-access)).

---

## Problem

`resolve_permissions()` is a pure union over a member's **Position** assignments — a
member holding no position has the empty permission set. That's correct for *write*
capability (which is the entire point of `roles-rbac.md`'s hard constraint: permissions
come only from positions), but it also means a member has **no read access at all**,
including to their own troop's event calendar or roster, until an admin manually assigns
them something.

In practice this means: a parent or scout invites → claims their account → logs in → and
gets a wall of 403s, because most members in most troops hold **no position** — the
Scoutmaster and a handful of committee members do, but the majority of scouts and parents
are just... members. That's the normal, expected shape of a troop, not an edge case, and
the current model treats it as "no access."

The fix is not a `Group` (groups are explicitly "no permissions, targeting-only" per
`roles-rbac.md` and mixing that in would break that separation). What's missing is a
**baseline permission set that comes from being a `Member` row in the tenant at all** —
independent of position.

---

## Decision

Add a seeded, system **`Member` Position**, automatically assigned to every `Member` at
creation time, mapped to a new **`Members` functional role** carrying a small baseline
read permission set. This keeps the existing hard rule intact — "a member's position
dictates what they can do; the only routine action is assigning a position" — rather than
special-casing an exception into `resolve_permissions()`. No new authorization code path;
it's just another row in the existing Position → FunctionalRole → Permission graph.

### Why a Position and not a permission-resolver special case

- `resolve_permissions()` stays a pure union over positions — no "if member has no
  positions, also union in X" branch to maintain or forget when the resolver is touched
  again later.
- The baseline permission set becomes **tenant-customizable** the same way every other
  functional role is (a troop could add `communication:*` to `Members` once messaging
  ships, with zero resolver changes) — via the existing Functional Roles admin screen.
- It's consistent with how the founder already gets a position (`Administrator`) assigned
  automatically at provisioning — this just extends "some members get positions assigned
  automatically" to "every member gets at least one."

### Baseline permission set

The seeded `Members` functional role grants:

| Permission | Why |
|---|---|
| `member:read` | See the roster — who's in the troop (name, patrol, type, primary position). Matches `members-screen.md`'s "Basic" tier. |
| `event:read` | See the event calendar. Already filtered per-event by `app/core/event_visibility.py` (troop-wide events + events for the caller's groups) — granting the gate doesn't grant seeing hidden events, it unblocks the endpoint that then applies that filter. |

**Explicitly not included:** `member:read_contact`, `member:read_medical`, any `*:write`,
`role:assign`, `report:read`, or anything admin/finance/advancement-related. Those remain
position-gated exactly as today.

> **Known pre-existing gap, not solved by this spec:** `member:read_contact` and
> `member:read_medical` exist as permissions in `roles-rbac.md`'s design but nothing in
> `app/routers/members.py` currently field-filters the `MemberRead` response based on
> them — `member:read` alone already returns the full record including contact and
> medical fields. This spec does not change or fix that; it only decides what gate a
> baseline member passes. Flagging it here because granting `member:read` to *every*
> member (rather than a curated few, as today) raises the stakes on that gap — it should
> be tracked as a follow-up, not silently absorbed into this change.

---

## Data model

### `Position.is_default` (new column, `TrackedBase` table `positions`)

```
is_default   bool   NOT NULL   default False
```

Marks a position that is **automatically assigned to every member** and is not a routine
per-member assignment choice. Only the seeded `Member` position sets this `True`. Distinct
from `is_system` (which just means "seeded, reconfigurable, not deletable" — `Administrator`
is `is_system` but not `is_default`; `Member` is both).

Migration: add the column (`server_default=false`), no RLS changes needed (existing table
already has policies).

### Seeded rows (`app/core/provisioning.py`)

- `DEFAULT_POSITIONS`: add `{"slug": "member", "name": "Member", "applies_to": ANY, "is_system": True, "is_default": True, "sort_order": <last>}`.
- `DEFAULT_FUNCTIONAL_ROLES`: add `{"slug": "members", "name": "Members", "is_system": True, "perms": [MEMBER_READ, EVENT_READ]}`.
- Map `member` → `members` in the position/functional-role wiring, same mechanism as every
  other default position.

---

## Auto-assignment

Every `Member` row gets a current (`end_date=None`) `MemberPositionAssignment` for the
tenant's `Member` position, created at the same time the `Member` row is:

1. **`POST /members`** (`app/routers/members.py::create_member`) — after inserting the
   `Member`, assign the baseline position. A helper `get_or_create_member_position(db,
   tenant_id)` (mirroring the existing `get_administrator_position`) resolves it, seeding it
   on first use for tenants provisioned before this spec shipped (belt-and-suspenders with
   the backfill below — provisioning seeds it for new tenants, this helper covers tenants
   that predate the change and haven't been backfilled yet).
2. **TWH importer** (`app/importers/twh.py`) — every imported `Person` → `Member` gets the
   same assignment, alongside whatever `Leadership_Position` history it imports.
3. **Tenant provisioning** (`provision_tenant` / `seed_default_rbac`) — the founder's
   `Member` row also gets the baseline `Member` position, *in addition to* `Administrator`.
   Redundant permission-wise (admin already has everything via `is_admin` short-circuit)
   but keeps the invariant simple: **every** `Member` row holds the `Member` position,
   no exceptions to remember.

No coupling to `membership_status` or claim state (`user_id`): an unclaimed or alumni
member still gets the assignment. It's inert until they can actually authenticate as that
member; this matches how no other position's currency is coupled to those fields today
either.

### Backfill for existing tenants

A one-time Alembic **data migration** (not just schema) that, for every tenant:

1. Ensures the `member` position + `members` functional role + mapping exist (idempotent —
   skip if a position with slug `member` already exists for that tenant, in case an admin
   already created one with a colliding slug).
2. For every `Member` row in that tenant without a **current** assignment of that position,
   creates one (`start_date` = migration run date).

Runs via `alembic upgrade head` like any other migration — no separate manual script step,
so self-hosted deployments and SaaS both pick it up the same way.

---

## API changes

- **`POST /members/{id}/positions`** (assign) and **`DELETE
  /members/{id}/positions/{assignment_id}`** (remove): reject (`409`) when the target
  position has `is_default=True`. It's not a routine assignment action — it's automatic,
  and letting an admin remove it manually would silently re-create the exact 403 wall this
  spec fixes, with no obvious cause. (`Administrator` remains manually assignable, subject
  to the existing "can't remove the tenant's last admin" 409 — only `is_default` positions
  get this new restriction, not all `is_system` ones.)
- **`GET /positions`** — unchanged; `member` is returned like any other position so the
  admin UI can inspect/retune the `Members` functional role's permissions.
- No change to `resolve_permissions()`, `event_visibility.py`, or any other read-path logic
  — this is purely "make sure the gate has something granting it by default."

---

## Self & family write access

Read access alone isn't the whole story — a member also needs to *maintain* their own
contact/medical info and manage their own event participation without holding `member:write`
/ `event:write` (which would also let them edit or RSVP for the entire roster, not just
themselves and their household).

### Events — already solved, no work needed here

`event-rsvp-permission.md` already specifies and implements this: `POST`/`PATCH`
`/events/{id}/participants` carry **no** `event:*` permission gate at all — only
`CurrentMemberDep` (any claimed member) plus `_require_can_act_for()`, which checks the
target `member_id` against `family_member_ids(caller.id, db)` (self + household, derived
from `MemberRelationship`; event managers bypass the check). This spec's baseline
`event:read` grant makes the *read* side of the same flow finally reachable (a member can
now see the event they're about to RSVP to); the *write* side needed nothing new.

### Members — new gap, needs the same pattern applied

No equivalent exists for `Member` records. `PATCH /members/{id}` is gated by a blanket
`member:write` — there is no self/family scope at all, so a plain member can't even fix a
typo in their own phone number without an admin holding `member:write`. This is the write-side
analogue of the exact problem this spec fixes for reads, and should be closed the same way
events was: reuse `family_member_ids()` rather than invent a second household-authorization
mechanism.

**Proposed change to `update_member`:** drop the blanket gate; branch instead:

- Caller holds `member:write` → unchanged, full `MemberUpdate` field set, any target member
  (today's behavior).
- Caller lacks `member:write` → allowed only if `member_id ∈ family_member_ids(caller.id,
  db)` (403 otherwise, same message shape as `_require_can_act_for`), **and** only for a
  restricted field allowlist — any other field present in the request body (even unchanged)
  is rejected (`403`/`422`, not silently dropped, so the client finds out immediately rather
  than assuming a save succeeded).

**Self/family-editable field allowlist** (contact + medical-disclosure fields a parent
normally maintains directly — matches what a paper BSA medical/contact form asks a family
to keep current, not administrative/identity/troop-record fields):

```
phone, address_line1, address_line2, city, state, postal_code, country, email,
emergency_contact_1_name, emergency_contact_1_phone,
emergency_contact_2_name, emergency_contact_2_phone,
medical_form_ab_date, medical_form_c_date, allergies, dietary_restrictions,
email_opt_out, sms_opt_in, nickname
```

**Explicitly admin-only (`member:write`), not in the allowlist:**

| Field(s) | Why not self/family-editable |
|---|---|
| `first_name`, `middle_name`, `last_name`, `name_suffix`, `date_of_birth` | Identity data tied to BSA registration and advancement age requirements — legal-name/DOB corrections should go through a leader, not be silently self-changed. |
| `bsa_id` | Registrar-controlled; self-editing risks duplicate/fraudulent registration matches. |
| `member_type`, `membership_status` | Administrative classification driving patrol/permission logic — not a personal preference. |
| `troop_membership_start_date`, `troop_membership_end_date` | Historical/administrative record. |
| `swim_classification`, `swim_date` | Safety-critical and verified by a leader/aquatics instructor at test time — not self-reported. |
| `email_bounced` | System/webhook-managed (once bounce handling ships — see `docs/resend-setup.md`'s "what this doesn't cover yet"), never user-set. |
| `notes` | Internal leader-facing notes field. |
| `oa_member`, `oa_active`, `oa_election_date`, `oa_call_out_date`, `oa_ordeal_date`, `oa_brotherhood_date`, `oa_vigil_date`, `oa_vigil_name`, `oa_notes` | Ceremony/troop-recorded facts (Vigil Honor etc.) — self-reporting these is a fraud vector. |
| `user_id` | Never editable via this endpoint at all — that's what the invite/claim flow is for. |

No schema split needed (`MemberUpdate` stays one schema); the allowlist check happens in
the handler against `body.model_dump(exclude_unset=True).keys()`.

---

## UI changes

**Hide, don't remove, from per-member displays.** The user-facing problem with showing
`Member` next to every person's name is exactly that — *every* person has it, so it adds
zero information and doubles as visual noise on every roster row and every member detail
view.

- `MemberPositionsEditor` (`apps/web/src/components/member-positions-editor.tsx`): filter
  `is_default` positions out of both the rendered badge list and the "add position" combobox
  options. A member who holds only the baseline position visually shows **no** position
  badges at all — not an empty-but-technically-populated one.
- Any other per-member "primary position" surface (members list table, member detail sheet)
  applies the same filter: `is_default` positions never surface as a badge/label tied to an
  individual.
- **`/positions` admin screen**: `Member` **is** shown, like any other `is_system` position
  (lock icon, no delete) — an admin configuring RBAC for the troop needs to see and retune
  what "every member" gets, e.g. adding a communications-read permission once messaging
  ships. This screen is about *configuring the position*, not *labeling a person*, so the
  suppression above doesn't apply here.
- The Positions admin screen should distinguish `is_default` positions with a short note
  (e.g. "Automatically held by every member" instead of/alongside the existing "System
  position" lock tooltip) so it's clear why it can't be un-assigned from the member side.

---

## Rollout risk

This is a permission change that applies **retroactively to every existing member in every
existing tenant** once the backfill migration runs — every scout and parent who previously
had zero permissions gains `member:read` + `event:read` the moment they log in. That's the
intended fix, but it's worth stating plainly: it is not scoped to new signups, it changes
what already-claimed accounts can see immediately on deploy. Recommend deploying with
attention to the migration step specifically (it's the actual behavior change; the
Terraform/app-code parts are comparatively low-risk) and spot-checking a claimed
non-admin account post-deploy.

---

## Testing

- New `Member` gets the baseline position assigned on `POST /members` (assignment row
  exists, currently active, resolves to `member:read` + `event:read` and nothing else).
- A member with **no other position** can `GET /members` and `GET /events` (200, not 403),
  but still gets 403 on `POST /members`, `member:read_contact`-gated fields (once/if that
  gap is fixed), and any admin-only route.
- `POST`/`DELETE .../positions` on the `member` position itself returns 409 regardless of
  caller permissions (including for `is_admin` callers — there's no legitimate reason to
  remove it, not even an override).
- TWH import assigns the baseline position to every imported `Person`.
- Backfill migration: existing member with no assignments gains a current one; existing
  member who (implausibly) already has a manually-created position with slug `member`
  is left alone (idempotency check does not double-assign or error).
- Frontend: `MemberPositionsEditor` renders no badge and offers no combobox entry for an
  `is_default` position; `/positions` page still lists it with the lock icon.
- A member with no `member:write` can `PATCH` their own `phone`/`address_line1`/etc.
  (allowlisted fields) on their own `member_id` (200).
- The same caller gets 403 attempting to `PATCH` a field **not** in the allowlist (e.g.
  `membership_status`, `bsa_id`) on themselves, even though the target is self.
- The same caller gets 403 attempting to `PATCH` any field — allowlisted or not — on a
  `member_id` outside `family_member_ids(caller.id, db)`.
- A parent (`parent_of`/`guardian_of` edge) can `PATCH` allowlisted fields on their linked
  child's `member_id`; an unrelated adult with no edge to that child cannot.
- A caller holding `member:write` is unaffected — full field set, any target — matching
  today's behavior exactly (regression check).

---

## Open questions

1. **Does `Members` need `event:read` scoped differently from the manager bypass?**
   `event_visibility.py` already lets `event:write` holders bypass audience filtering.
   Baseline `event:read` holders get normal audience filtering (troop-wide + their groups)
   — no change needed, just confirming this spec doesn't need to touch that file.
2. **Should `is_default` positions be excluded from `applies_to` scope filtering in the UI
   (position pickers elsewhere)?** Likely moot since it's filtered out of pickers entirely,
   but worth confirming there's no other position-selection surface (e.g. bulk import
   mapping) that needs the same filter.
3. **Should `email` be in the self/family allowlist?** It's included above (a member's own
   contact email is exactly the kind of thing they should maintain themselves), but flagging
   it because `email` also participates in the invite flow's user-lookup
   (`invite_admin_member` matches an existing `User` by email at *invite-creation* time,
   before claim). Editing it post-claim doesn't touch that path, so this should be safe, but
   worth a second look before implementing.
4. **Frontend surface for self/family edit.** This spec defines the backend authorization
   change; it doesn't design the UI (e.g. does the existing `/members/{id}/edit` form
   detect "I lack member:write but this is me/my kid" and render only the allowlisted
   fields, or is that a separate, simpler "My Profile" view?). Worth scoping before
   implementation — noting it here so it isn't silently assumed either way.
