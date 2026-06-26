# Tenant Switcher Spec

**Status:** Draft
**Routes:** `GET /auth/memberships` (new)
**Pillars:** Web Application Shell · Roster & Relationships (Pillar 1)
**Related:** [`session-permissions.md`](session-permissions.md) (per-tenant session),
[`tenant-data-access.md`](tenant-data-access.md) (the bypass path this endpoint uses).

---

## Overview

A `User` can be a `Member` of several tenants (a parent in two troops; a leader who is
also a parent elsewhere). The app must let them pick **which troop they are acting in**
and then show data for **exactly one tenant at a time** — never a merged cross-tenant
view. This makes "active tenant" a first-class, explicit concept instead of a build-time
constant, and it directly supports on-device isolation for the future mobile client
(partition the local store by active tenant).

Today the web app hardcodes a single tenant via the `NEXT_PUBLIC_TENANT_ID` build-time
env var (`apps/web/src/lib/api.ts`), so there is no notion of switching at all. This
spec replaces that constant with a runtime selection.

---

## Backend

### Endpoint

```
GET /auth/memberships
Headers: Authorization: Bearer <jwt>
```

No `X-Tenant-ID` required — this is the one read that is **legitimately cross-tenant for
a single user**: "which troops am I a member of?" Returns the caller's non-deleted
`Member` rows across all tenants, joined to tenant name/slug:

```jsonc
[
  { "tenant_id": "…", "tenant_name": "Troop 123", "tenant_slug": "troop123",
    "member_id": "…", "is_admin": true },
  { "tenant_id": "…", "tenant_name": "Pack 9",    "tenant_slug": "pack9",
    "member_id": "…", "is_admin": false }
]
```

- Lives in `app/routers/auth.py`, gated by auth only (like `/auth/me`), **not** by
  `require()` or a tenant.
- Runs on the **`unscoped()` / bypass path** ([`tenant-data-access.md`](tenant-data-access.md))
  because it reads across tenants — but the query **must** still constrain
  `Member.user_id == current_user.id`. Bypass removes tenant scoping, never the user
  constraint.
- Excludes suspended tenants from the switchable list (a suspended tenant rejects
  tenant-scoped requests anyway), or flags them disabled — implementer's call; default
  to excluding.
- Empty list is valid (a platform admin with no memberships) → the UI shows a "no troops"
  state, consistent with the `member: null` case in `session-permissions.md`.

---

## Frontend

### Active-tenant state

Replace the static `NEXT_PUBLIC_TENANT_ID` read with a runtime **active tenant**:

- A small `TenantProvider` (React context) holds `activeTenantId`, seeded from (in order)
  the subdomain if present, else `localStorage`, else the first membership, else null.
- `useApi()` sources `X-Tenant-ID` from this provider instead of the env var.
- `NEXT_PUBLIC_TENANT_ID` may remain as a dev convenience default, but it is no longer
  the source of truth.

### Switcher UI

- A pulldown in the app shell (sidebar footer near the `UserButton`, or the header),
  populated from `GET /auth/memberships`.
- Hidden / rendered as a static label when the user has exactly one membership (no point
  switching).
- Selecting a tenant updates `activeTenantId`.

### Subdomain vs. header reconciliation

Tenant is resolved subdomain-first in production (`troop123.opentroop.app`) and by
`X-Tenant-ID` otherwise (`app/core/tenant.py`). The switcher honors both:

- **Subdomain mode (prod):** switching navigates to the target tenant's subdomain
  (`window.location` to `troop123.opentroop.app`). The subdomain stays the source of
  truth; a full reload naturally clears all cached state.
- **Header mode (dev / single-origin):** switching updates `activeTenantId` in place;
  no navigation. The cache reset below handles staleness.

### Query cache on switch — the cross-cutting part

Every React Query key must be scoped to the active tenant so tenant A's cached data is
never shown under tenant B. Currently only `use-session.ts` keys by tenant; the rest use
plain keys (`["members"]`, `["events"]`, …).

- Introduce a `tenantKey(...)` helper (or a thin `useTenantQuery` wrapper) that prefixes
  every key with the active tenant id, and adopt it across `src/hooks/use-*.ts`.
- On in-place switch (header mode), also `queryClient.clear()` (or invalidate all) as a
  belt-and-suspenders guard against any key that wasn't migrated.
- The `["session", tenantId]` key from `session-permissions.md` already follows this
  pattern and needs no change.

This key refactor is the bulk of the frontend work and should be called out as such in
the issue.

---

## Security note

The switcher is **UX only** — it sets which tenant the client *asks* about. The backend
re-resolves the tenant on every request and `require()` still enforces per-tenant
permissions. Selecting a tenant the user has no `Member` in yields the graceful
`member: null` session state, not elevated access. A user cannot switch into a tenant
absent from their `/auth/memberships` list and gain anything — the server gates every
call independently.

---

## Testing

**Backend:**

- `GET /auth/memberships` returns exactly the caller's non-deleted memberships across
  tenants; a user in A and B sees both; a user in only A sees only A.
- The `user_id == me` constraint holds inside the bypass — another user's memberships
  never appear.
- Suspended tenants are excluded (or flagged) per the chosen default.
- Soft-deleted `Member` rows are excluded.

**Frontend:**

- Switcher lists the memberships from the endpoint; hidden for a single membership.
- Switching updates the `X-Tenant-ID` sent by `useApi()` and refetches tenant-scoped
  queries (no stale tenant-A data under tenant B).
- One-tenant-at-a-time: no view merges rows from two tenants.

---

## Out of scope / future

- **Mobile switcher + multi-tenant local store partitioning** — same "active tenant"
  concept; the on-device isolation it enables is tracked under Mobile Applications.
- **Cross-tenant aggregate views** for users in many troops (e.g. a combined calendar) —
  explicitly *not* this feature; this spec enforces single-tenant viewing.
- **Invitations / joining a new tenant from the switcher** — handled by the existing
  invite/claim flow, not here.
