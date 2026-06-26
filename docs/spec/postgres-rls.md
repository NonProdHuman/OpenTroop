# Postgres Row-Level Security (RLS) Spec

**Status:** Draft
**Scope:** Database layer — Alembic migrations, DB roles, `app/core/database.py`
**Pillars:** Roster & Relationships (Pillar 1) — multi-tenant foundation
**Related:** [`tenant-data-access.md`](tenant-data-access.md) (app-layer half of the
same defense), Text-to-SQL read-replica guard in `ROADMAP.md`.

---

## Overview

Postgres Row-Level Security makes the **database itself** refuse to return or write rows
outside the current tenant, regardless of what the application query asks for. It is the
**database-layer** half of a two-layer defense; the **application-layer** half is the
automatic tenant-scoped session in [`tenant-data-access.md`](tenant-data-access.md).
Both read the same current-tenant value.

The two layers are complementary, not redundant:

| | App layer (`tenant-data-access.md`) | DB layer (this spec) |
|---|---|---|
| Mechanism | `with_loader_criteria` on `TrackedBase` | `CREATE POLICY` per table |
| Catches | The common case, ergonomically | The query that bypassed the app layer |
| Runs on | SQLite + Postgres | Postgres only |
| Failure if omitted | leak | leak |

RLS is **not** a replacement for the app layer — it's the backstop for the one query
someone writes with raw SQL, a missed `unscoped()`, or a future code path that forgets
the convention. Keep both.

---

## Design

### Restricted application role

RLS is bypassed by the table owner and any `BYPASSRLS` role. So the app must connect as
a **non-owner, non-superuser role** for tenant traffic:

- `opentroop_app` — owns nothing, has `SELECT/INSERT/UPDATE/DELETE` on tenant tables,
  **RLS enforced**. This is the default `DATABASE_URL` role.
- `opentroop_admin` — migrations/DDL owner (or a role with `BYPASSRLS`) used by the
  **platform control plane** and Alembic. Maps to the `unscoped()` path in the app
  layer. A separate connection/session, never the default request path.

### Session tenant variable (GUC)

Policies match rows against a per-transaction setting. The same dependency that sets the
app-layer ContextVar issues, on the request's transaction:

```sql
SET LOCAL app.current_tenant = '<uuid>';
```

`SET LOCAL` scopes the value to the current transaction, so it **cannot leak across
pooled connections** — critical with SQLAlchemy's connection pool. Wire it via a
transaction-begin event listener on the session so every transaction is stamped before
any tenant query runs.

### Policies

Enabled per `TrackedBase` table, generated from the model registry rather than
hand-written per table:

```sql
ALTER TABLE members ENABLE ROW LEVEL SECURITY;
ALTER TABLE members FORCE ROW LEVEL SECURITY;  -- applies to table owner too

CREATE POLICY tenant_isolation ON members
  USING      (tenant_id = current_setting('app.current_tenant')::uuid)
  WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

- `USING` governs which rows are **visible** to SELECT/UPDATE/DELETE.
- `WITH CHECK` governs which rows may be **written** by INSERT/UPDATE — this is what
  stops a buggy or hostile client (notably the mobile sync push path) from writing rows
  *into* another tenant.
- `FORCE ROW LEVEL SECURITY` ensures even the table owner is subject to policy, so the
  boundary doesn't depend on which role happens to connect.

A migration helper iterates `Base.metadata` for `TrackedBase` subclasses and emits the
`ENABLE/FORCE/CREATE POLICY` trio for each, so new tenant tables are covered by adding
the table — no per-table boilerplate.

### `is_deleted` and policies — do not conflate

Policies match on **`tenant_id` only**. Do **not** add `is_deleted = false` to the
policy: soft-delete filtering belongs in the app layer, and the mobile sync pull must be
able to read `is_deleted = true` tombstones (which share the tenant) to converge
deletions on-device. An over-eager policy would silently break sync.

### Platform / cross-tenant paths

- The control plane connects as `opentroop_admin` (BYPASSRLS) and is already gated by
  `PlatformAdminDep`. It pairs with `unscoped()` in the app layer.
- `GET /auth/memberships` reads the caller's own `Member` rows across tenants. It runs on
  the bypass path **but still filters `user_id == me`** — RLS-off removes tenant scoping,
  never the user constraint.

---

## Sync interactions (mobile, offline-first)

RLS lives on the **backend ↔ Postgres** boundary; the mobile app talks to FastAPI, not
Postgres, so RLS does not change offline-first mechanics. But it hardens the
highest-blast-radius part of sync:

- **Pull (delta read):** a sync payload that leaks a cross-tenant row gets *persisted* on
  the wrong device and re-uploaded later — far worse than a transient screen leak. RLS
  guarantees the payload is tenant-clean even if the pull query is wrong.
- **Push (write-back):** offline-created rows carry client-generated UUIDv7 PKs and a
  `tenant_id`; `WITH CHECK` rejects any that don't match the session tenant.
- **Tombstones:** preserved (see above) — policy must stay `tenant_id`-only.
- **On-device isolation is NOT covered.** If a device ever caches more than one tenant,
  isolating them locally is the mobile app's job (partition by active tenant — see
  [`tenant-switcher.md`](tenant-switcher.md)). RLS stops at the server.

---

## Testing

The SQLite suite **cannot** exercise RLS (Postgres-only). The resolution is a small,
separate Postgres-backed tier rather than abandoning SQLite. Three layers:

1. **SQLite suite (default, unchanged):** the ~250 functional tests + the app-layer
   tenant filter. Stays fast and infra-free — `uv run pytest` needs no Postgres. Preserves
   the contributor inner loop and the project's DB-free principle.
2. **Postgres RLS tier — runs on every PR:** ~10 tests behind a `pg` marker (e.g.
   `tests/rls/`), proving the database enforces the boundary. **Gated per-PR, not
   nightly** — see rationale below. Locally it is opt-in: skipped unless a test Postgres
   is configured (reuse the `docker-compose` Postgres); CI provides it via a service
   container.
3. **Optional full-suite-on-Postgres (scheduled/nightly):** the engine fixture is
   parametrizable by env var so the *entire* suite can run on Postgres on demand. This is
   the **only** place scheduled CI is appropriate — catching dialect drift (partial
   indexes, enums, JSON), **not** the RLS boundary.

### Why the RLS tier is per-PR, not nightly

Nightly is for slow, flaky, or expensive checks. The RLS tests are none of those — a
handful of millisecond assertions whose only cost is ~10–20s of container startup.
Meanwhile they guard the tenant-isolation backstop of a multi-tenant SaaS holding minors'
PII. The likely regressions merge silently (a new `TrackedBase` table with no policy; a
migration that drops one; a role-grant change). Trivial cost to run, catastrophic cost to
miss — so it gates at the door, not the morning after.

### The RLS tier runs against a *migrated* database

Roles and policies live in **migrations**, not `Base.metadata`, so this tier runs
`alembic upgrade head` and connects as the restricted `opentroop_app` role (not the
owner). Side benefit: it is the project's first **migrations-apply-cleanly** check in CI,
which does not exist today.

### Tests in the tier

- **Policy completeness (highest value):** introspect `Base.metadata` for every
  `TrackedBase` subclass and assert each table has `relrowsecurity` set and a matching
  `pg_policies` row. Catches the "new table, forgot the policy" regression automatically,
  forever.
- With `app.current_tenant = A`, a **raw** `SELECT * FROM members` (no WHERE) returns only
  tenant-A rows — enforcement without any app-layer help.
- An INSERT/UPDATE with a mismatched `tenant_id` is rejected by `WITH CHECK`.
- Tombstones (`is_deleted = true`) within the tenant remain visible (sync safety).
- The `opentroop_admin` / `unscoped()` path reads across tenants; default `opentroop_app`
  cannot.
- A missing/blank `app.current_tenant` GUC yields **zero** rows (fail-closed), not all.

---

## Out of scope / future

- **App-layer auto-scoping** — [`tenant-data-access.md`](tenant-data-access.md);
  recommended to land first so RLS is a backstop, not the sole boundary.
- **Read-replica RLS for Text-to-SQL** — the read-only replica path in `ROADMAP.md`
  should reuse the same role + GUC model; specced with that feature.
- **Per-row / per-column policies** (e.g. medical-data visibility) — RBAC handles that at
  the endpoint layer today; revisit only if a DB-level need emerges.
