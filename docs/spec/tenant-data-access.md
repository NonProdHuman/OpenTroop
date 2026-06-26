# Tenant-Scoped Data Access Spec

**Status:** Draft
**Scope:** Backend data layer (`app/core/database.py`, `app/core/deps.py`, all routers)
**Pillars:** Roster & Relationships (Pillar 1) — multi-tenant foundation
**Related:** [`postgres-rls.md`](postgres-rls.md) (DB-layer backstop),
[`tenant-switcher.md`](tenant-switcher.md) (UI that selects the active tenant).

---

## Overview

Tenant isolation today is enforced by **hand-written `tenant_id == tenant_id`
predicates on every query** — roughly 200 of them across 13 router modules, plus the
`get_or_404` helper. The boundary is re-derived by hand at every call site, so the
failure mode is simple and recurring: *a developer forgets one `.where()` and that
endpoint leaks across tenants.* This is not hypothetical — the `GET /auth/session`
`roles` lookup shipped missing its `tenant_id` filter and was caught only in review.

This spec makes tenant scoping **automatic and default-on**. A request-scoped current
tenant is injected into every ORM read and stamped onto every ORM write, so route code
no longer carries the tenant predicate. Forgetting it becomes structurally impossible
rather than a review checklist item. Cross-tenant access becomes an **explicit,
greppable opt-out** used only by the platform control plane.

This is the **application-layer** half of a two-layer defense. The **database-layer**
half is Postgres Row-Level Security ([`postgres-rls.md`](postgres-rls.md)); both read
the same current-tenant value. The app layer keeps queries efficient and
intention-revealing and keeps the SQLite test suite meaningful; RLS is the hard backstop
that catches anything the app layer misses.

---

## Design

### Current-tenant context

A request-scoped `ContextVar[uuid.UUID | None]` holds the active tenant:

```python
# app/core/tenant_context.py
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("current_tenant", default=None)
_bypass: ContextVar[bool] = ContextVar("tenant_bypass", default=False)

def set_current_tenant(tenant_id: uuid.UUID) -> None: ...
def current_tenant() -> uuid.UUID | None: ...

@contextmanager
def unscoped():
    """Disable automatic tenant filtering for cross-tenant platform work.

    The only sanctioned way to read across tenants. Greppable, auditable, and
    paired with the BYPASSRLS DB role (see postgres-rls.md) so it actually works
    when RLS is enabled.
    """
    token = _bypass.set(True)
    try:
        yield
    finally:
        _bypass.reset(token)
```

The existing `get_tenant_id` dependency (`app/core/tenant.py`) already resolves the
tenant from subdomain or `X-Tenant-ID`. A thin dependency layered on top calls
`set_current_tenant(...)` (and, once RLS lands, issues `SET LOCAL app.current_tenant`)
so the ContextVar and the DB session GUC share one source of truth.

### Automatic read filtering

A `do_orm_execute` event listener applies a tenant predicate to every ORM SELECT
touching a `TrackedBase` entity — including entities pulled in via relationship loads —
unless the request is `unscoped()`:

```python
from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria
from app.models.base import TrackedBase

@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state):
    if _bypass.get():
        return
    tid = current_tenant()
    if tid is None or not state.is_select:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TrackedBase,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        )
    )
```

Because the criterion targets `TrackedBase`, it applies to **every** tenant-scoped
model automatically and to future ones for free. `PlatformBase` entities (Tenant, User,
Identity) have no `tenant_id` and are untouched — platform reads work unchanged.

> **`is_deleted` is out of scope here.** This layer owns *only* the `tenant_id`
> predicate. Soft-delete filtering stays explicit in route code (and must, so that sync
> tombstone reads can opt in to seeing deleted rows). RLS likewise governs tenant_id
> only — see [`postgres-rls.md`](postgres-rls.md).

### Automatic write stamping

Reads are filtered; writes must be *stamped*. A `before_flush` hook (or a mapper-level
default sourced from the ContextVar) sets `tenant_id` on any new `TrackedBase` instance
that doesn't already have one:

```python
@event.listens_for(Session, "before_flush")
def _stamp_tenant(session, flush_context, instances):
    if _bypass.get():
        return
    tid = current_tenant()
    if tid is None:
        return
    for obj in session.new:
        if isinstance(obj, TrackedBase) and obj.tenant_id is None:
            obj.tenant_id = tid
```

This removes `tenant_id=...` from the `*Create` paths and prevents the inverse leak —
accidentally writing a row into the wrong tenant. The RLS `WITH CHECK` clause is the
backstop here too.

### The platform bypass

Cross-tenant access is legitimate in exactly two places, both of which opt out
explicitly:

- **Platform control plane** (`app/routers/platform.py`) — provisioning, listing, and
  inspecting tenants. Wrapped in `unscoped()` and run under the BYPASSRLS DB role.
- **"My memberships" lookup** (`GET /auth/memberships`, see
  [`tenant-switcher.md`](tenant-switcher.md)) — reads the caller's own `Member` rows
  across all tenants. Uses `unscoped()` but **must** still filter `Member.user_id == me`
  in the query; the bypass removes tenant scoping, not the user constraint.

Everything else inherits automatic scoping and never thinks about it.

---

## Migration path

This is a behavior-preserving refactor that can land incrementally:

1. Add `tenant_context.py`, the dependency wiring, and the two event listeners.
   With the ContextVar set, existing explicit filters become **redundant but harmless**
   (the same predicate applied twice).
2. Verify the full suite still passes with both layers active (belt-and-suspenders).
3. Remove the now-redundant hand-written `tenant_id ==` predicates router by router,
   relying on the automatic layer. Keep `get_or_404`'s tenant check until RLS lands,
   then it too becomes a backstop.
4. Add a lint/CI check (or a periodic audit) that flags any **new** `unscoped()` call
   in a non-platform module for human review.

Steps 1–2 add safety immediately; step 3 is cleanup that can proceed at leisure.

---

## Testing

The SQLite test suite stays DB-free and validates the **application** layer:

- A query with no explicit `tenant_id` filter, issued with the ContextVar set to tenant
  A, returns only tenant-A rows even when tenant-B rows exist (the core guarantee).
- A new `TrackedBase` row created with the ContextVar set to A is stamped `tenant_id = A`
  without the caller passing it.
- `unscoped()` returns cross-tenant rows; the `Member.user_id == me` constraint still
  narrows the memberships query inside `unscoped()`.
- Relationship loads (e.g. `Event.location`) are tenant-filtered, not just top-level
  selects.
- The conftest fixtures set the ContextVar from the same `X-Tenant-ID` header they
  already use, so existing tests need no per-test changes.

The **database** layer (RLS enforcing the boundary even with no app-layer filter) is
validated by a separate Postgres-backed suite — see [`postgres-rls.md`](postgres-rls.md).

---

## Out of scope / future

- **RLS itself** — [`postgres-rls.md`](postgres-rls.md).
- **Soft-delete default filtering** — could get the same automatic treatment later, but
  needs an opt-in for sync tombstone reads; deferred.
- **Read replica routing** for the Text-to-SQL feature — that path has its own
  tenant-guard story in the roadmap; this layer's `unscoped()` is not a substitute.
