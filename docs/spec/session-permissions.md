# Session & Permissions Spec

**Status:** Draft
**Routes:** `GET /auth/session` (new)
**Pillars:** Roster & Relationships (Pillar 1) — RBAC surface · Web Application Shell
**Prerequisite for:** permission-filtered navigation and action buttons
(see [`docs/spec/navigation.md`](navigation.md) and `ROADMAP.md`).

---

## Overview

The web app needs to know **what the signed-in user is allowed to do in the current
troop** so it can hide navigation sections and action buttons the user can't use. Today
it can't: the only identity endpoint is `GET /auth/me`, which returns the platform
`User` (cross-tenant identity + `platform_role`) and carries **no tenant permissions**.

Permissions live on the **`Member`** side (`MemberRoleAssignment` → roles →
`RolePermission`), resolved by `resolve_permissions(member_id, session)` into a
`frozenset[Permission]`. The backend already enforces them via `require(permission)` on
every route; this spec exposes the *same* resolved set to the frontend for UX gating.

### User vs. Member (why a new endpoint)

| | `User` (`/auth/me`) | `Member` (this spec) |
|---|---|---|
| Scope | Platform (cross-tenant) | One tenant |
| Cardinality | One per person | One per person **per tenant** |
| Carries | `platform_role` | roles → permissions |

A `User` may be a `Member` of several tenants with different permissions in each, so the
new data is **tenant-scoped** (resolved from `X-Tenant-ID`) and distinct from
`/auth/me`. `/auth/me` stays platform-only and unchanged.

---

## Actors and Permissions

Any authenticated user may call `GET /auth/session` — it reports *their own* access and
requires no specific permission. A user with no `Member` in the active tenant gets a
valid "no access" response (see below), not an error.

---

## Backend

### Endpoint

```
GET /auth/session
Headers: Authorization: Bearer <jwt>, X-Tenant-ID: <tenant>
```

Resolves the caller's `User` from the JWT and their `Member` in the tenant from
`X-Tenant-ID`, then returns the member plus their effective permission set.

### Response — `SessionRead`

```jsonc
{
  "tenant_id": "…uuid…",
  "member": { /* MemberRead, or null */ },
  "permissions": ["event:create", "event:read", "member:read", "member:write"],
  "roles": [{ "id": "…uuid…", "name": "Scoutmaster" }]
}
```

- `member` — `MemberRead` for the caller's member in this tenant, or **`null`** when the
  user has no member here.
- `permissions` — sorted `list[Permission]` from `resolve_permissions(member.id)`. Empty
  when `member` is null. For an `is_admin` role this is the **full** `Permission` set
  (the resolver already short-circuits), so the frontend needs no admin special-casing.
- `roles` — the member's directly-assigned roles (id + name) for role-based UI; empty
  when `member` is null. (Directly-assigned only — not the transitively-inherited
  functional groups; the resolved `permissions` already account for inheritance.)

### The "not a member" case

A signed-in user may legitimately have **no `Member`** in the active tenant — a platform
admin browsing a troop, or an invitee who hasn't claimed yet. Unlike
`get_current_member` / `require()` (which raise **403**), this endpoint returns **200**
with `member: null, permissions: []`. Rationale: "tell me who I am here" is not a
protected action; a 200 lets the app shell render a graceful "no access in this troop"
state instead of treating it as an error. (Protected *actions* still 403 via
`require()`.)

A **suspended** tenant is still rejected at tenant resolution (403), unchanged.

### Schema & wiring

- New `SessionRead` in `app/schemas/session.py` (or alongside `auth`):
  `tenant_id: uuid.UUID`, `member: MemberRead | None`, `permissions: list[Permission]`,
  `roles: list[SessionRoleRead]` where `SessionRoleRead = { id, name }`.
- New handler in `app/routers/auth.py`. It cannot reuse `CurrentMemberDep` (that raises
  403 on no-member); instead it does the same `user_id + tenant_id` lookup inline and
  tolerates `None`.
- `permissions` is `sorted(resolve_permissions(member.id, db))` (stable order for
  caching/diffing/tests).

### Errors

| Condition | Status |
|---|---|
| Missing/invalid JWT | 401 (existing auth dependency) |
| Missing/invalid tenant, or suspended tenant | 403 (existing tenant resolution) |
| Authenticated, no member in tenant | **200** with `member: null` |
| Authenticated member | 200 |

---

## Frontend

### Types

Add a `Permission` string-union to `src/types/api.ts` mirroring the backend enum
(`"member:read" | "member:write" | … | "report:read"`), plus a `Session` interface
matching `SessionRead`. Keeping the union in sync with the enum is a manual mirror, same
as the other hand-written types (per `apps/web/CLAUDE.md`).

### Hook

`src/hooks/use-session.ts`:

```ts
export function useSession()       // useQuery(["session", tenantId], () => GET /auth/session)
export function usePermissions() {
  const { data } = useSession()
  const set = new Set(data?.permissions ?? [])
  return {
    has: (p: Permission) => set.has(p),
    isMember: data?.member != null,
    isLoading: …,
  }
}
```

- Query key includes the tenant so switching tenants refetches.
- While loading, `has()` returns `false` — nav/buttons render their unauthorized
  (hidden/disabled) state until the set arrives, avoiding a flash of forbidden actions.

### Consumption

- **Navigation** — the nav registry in `app-sidebar.tsx` gains an optional
  `requires?: Permission` per item/child; items are filtered with `has(item.requires)`.
  This generalizes today's `platformOnly` flag (which stays for `platform_role`).
- **Action buttons** — gate with `has(...)`: e.g. *Add Member* behind `member:write`,
  *Add Event* behind `event:create`. Hidden (not merely disabled) when absent, matching
  the sidebar.

### Cache invalidation

Permissions change when roles are assigned/revoked. The role-assignment mutations
(`use-role-assignments.ts`) should `invalidateQueries({ queryKey: ["session"] })` on
success. Otherwise staleness is acceptable (roles rarely change mid-session); no polling.

---

## Security note (read this)

Client-side gating is **UX only** — it prevents *showing* actions that would 403. It is
**not** an access control. Every protected route keeps its `require(permission)`
dependency as the real enforcement boundary. A spoofed/edited `permissions` array on the
client gains nothing: the server re-checks on every call.

---

## Testing

**Backend** (`tests/test_api_auth.py` or new `test_api_session.py`):

- Admin member → `permissions` is the full set; `member` non-null; `roles` includes the
  admin role.
- Non-admin member with a known role → `permissions` is exactly that role's resolved set
  (assert a couple are present and an unrelated one is absent).
- Authenticated user with **no member** in the tenant → 200, `member: null`,
  `permissions: []`.
- Cross-tenant: same user, two tenants with different roles → different permission sets
  per `X-Tenant-ID`.
- Missing tenant / suspended tenant → 403; missing auth → 401.

**Frontend**:

- `usePermissions().has()` reflects the fetched set; returns `false` while loading.
- Sidebar hides an item whose `requires` permission is absent and shows it when present.
- An action button (e.g. Add Member) is hidden without `member:write`.

---

## Out of scope / future

- **Tenant switcher UI** — the endpoint is already per-tenant; a switcher just changes
  `X-Tenant-ID` and the query key. Separate feature.
- **Server-side caching** of `resolve_permissions` — fine to add later if profiling
  warrants; the resolver is a few indexed queries per session load today.
- **Relationship-scoped access** (e.g. a parent reading only their own child) — enforced
  at the endpoint layer, not via the coarse `permissions` set; out of scope here.
