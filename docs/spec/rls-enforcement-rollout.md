# RLS Enforcement Rollout & Cutover Plan

**Status:** Draft — execution plan, not a design doc
**Scope:** `app/core/database.py`, `app/core/tenant_context.py`, `app/core/deps.py`,
`alembic/env.py`, the RLS migration(s), the routers, CI
**Pillars:** Multi-Tenant Isolation & Data Access (Pillar 2)
**Related (design):** [`tenant-data-access.md`](tenant-data-access.md) (app-layer half),
[`postgres-rls.md`](postgres-rls.md) (DB-layer half). This spec is the **rollout** that
finishes both and turns enforcement on without breaking the app or migrations.

---

## Goal

Get to **RLS actually enforcing** the tenant boundary in production — the database
refusing cross-tenant rows even when the app layer is wrong or bypassed — with:

- no remaining redundant per-query `tenant_id ==` predicates in normally-scoped routes,
- every legitimate cross-tenant path explicitly on the bypass,
- migrations that keep applying cleanly under the enforced regime, and
- a one-line, reversible final flip rather than a big-bang change.

This is sequenced so the risky part (turning on `FORCE`) is the *last, smallest* step,
preceded by changes that are individually behavior-preserving and shippable on their own.

---

## Current state (audit)

What is already true today (verified in the tree):

- ✅ The app-layer engine is live: `app/core/database.py` has the `do_orm_execute` read
  filter, the `before_flush` write stamp, and an `after_begin` hook that issues
  `SET LOCAL app.current_tenant`. `app/core/tenant_context.py` provides the ContextVar
  and `unscoped()`.
- ✅ Migration `09a1b2c3d4e5` creates roles `opentroop_app` (RLS-enforced) and
  `opentroop_admin` (`BYPASSRLS`), enables RLS, and installs the `tenant_isolation`
  policy + grants on every `TrackedBase` table.

What is **not** true yet — the gap this plan closes:

- ❌ **RLS is dormant.** No `FORCE ROW LEVEL SECURITY`, and `DATABASE_URL` connects as
  the table **owner** (`opentroop`), which bypasses RLS automatically. The policies are
  installed but never consulted.
- ❌ **The dedicated roles are unused at runtime.** Nothing in `app/` ever connects as
  `opentroop_app` / `opentroop_admin`; there is a single engine/session
  (`app/core/database.py`), not separate app/admin pools.
- ❌ **Redundant predicates remain.** ~21 `tenant_id ==` clauses across 10 routers
  (`members.py`, `events.py`, `roles.py`, `groups.py`, `locations.py`, `event_types.py`,
  `role_assignments.py`, `relationships.py`, `auth.py`, `platform.py`) — step 3 of
  [`tenant-data-access.md`](tenant-data-access.md) is unfinished.
- ❌ **Cross-tenant paths aren't all on `unscoped()`.** Only `auth.py` uses it. The
  platform control plane (`platform.py`, `provisioning.py`) works today only because it
  sets no tenant (`current_tenant()` is `None`, so the app filter no-ops) **and** the
  owner bypasses RLS. Under enforcement, a no-tenant request fails **closed** (empty GUC →
  zero rows), so these paths break unless they explicitly bypass.
- ❌ **Migrations have no bypass role.** `alembic/env.py` connects with the plain
  `DATABASE_URL` and never `SET ROLE`s. Fine while that role is the owner; broken once it
  is the restricted `opentroop_app`.
- ❌ **The RLS migration introspects live models** (`TrackedBase.__subclasses__()` at run
  time), so an applied revision does not cover tables added later, and a fresh apply
  covers whatever models exist *now* — not reproducible.

---

## Plan

Four phases. **Phase 0, A, and B are behavior-preserving** and can each merge
independently. **Phase C** is the actual flip and is reversible.

### Phase 0 — Finish the app-layer predicate cleanup

Completes step 3 of [`tenant-data-access.md`](tenant-data-access.md). The auto-filter
already applies the tenant predicate to every scoped read, so the hand-written ones are
redundant **in scoped request paths** — but not everywhere.

**Classification rule (do not blindly delete all 21):**

| Where the predicate lives | Action |
|---|---|
| A normal tenant-scoped route (request carries `TenantDep`) | **Remove** — the auto-filter covers it |
| Inside an `unscoped()` block, or in the platform plane (no tenant set) | **Keep** — load-bearing; the auto-filter is off there |
| A `user_id == me` (or similar non-tenant) constraint | **Keep** — never a tenant predicate |
| `get_or_404`'s tenant check | **Keep until Phase C**, then it becomes a backstop |

Per router: remove the redundant clause, run the suite (SQLite proves the auto-filter
still scopes the query), repeat. Then complete step 4: a CI lint/audit that flags any
**new** `unscoped()` outside the platform/auth allowlist for human review.

**Exit:** the only `tenant_id ==` predicates left in the codebase are the load-bearing
ones in bypass/platform paths and non-tenant constraints.

### Phase A — Put every cross-tenant path explicitly on the bypass

Today the platform plane relies on "no tenant set + owner bypass." Make the bypass
**explicit** so it survives enforcement:

- Wrap every cross-tenant `TrackedBase` access in `unscoped()`: `platform.py`,
  `provisioning.py`, and the `auth` memberships/claim paths that read across tenants.
  Reads of `PlatformBase` entities (Tenant, User, Identity) need nothing — they have no
  `tenant_id` and no policy.
- Keep the `Member.user_id == me` constraint inside the memberships `unscoped()` block —
  the bypass removes tenant scoping, never the user constraint.

This is invisible today (`unscoped()` only toggles the app filter, which is already a
no-op when no tenant is set), so it ships with zero behavior change — but it is the hook
Phase B uses to pick the DB role.

**Exit:** `grep -rn unscoped app/` enumerates *every* legitimate cross-tenant operation,
and the platform/auth suites pass with the bypass in place.

### Phase B — Wire the real DB roles via *physically separate* connections

> **Why separate pools, not `SET LOCAL ROLE`.** The data at risk is minors' PII and
> health records, so the bypass capability must be **unreachable** from a scoped request —
> not merely unused. With one connection that `SET ROLE`s per transaction, a single
> mis-ordering, an exception that skips the reset, or a forgotten `SET LOCAL` re-exposes
> `BYPASSRLS` on a request path. With two physical pools, an app-pool connection
> authenticates as a role that **has no `BYPASSRLS` and no grant to a role that does** —
> there is no in-band way for a tenant request to cross tenants, full stop. The cost
> (a second small pool) is trivial because admin/cross-tenant traffic is minimal.

Three roles, three connection strings, least-privilege:

| Role | `BYPASSRLS` | Owns tables | DML grants | Used by |
|---|---|---|---|---|
| `opentroop_app` | no (RLS enforced) | no | yes | **App engine** — all tenant request traffic (`DATABASE_URL`) |
| `opentroop_admin` | yes | no | yes | **Admin engine** — cross-tenant runtime paths (`DATABASE_URL_ADMIN`) |
| owner (e.g. `opentroop_owner`) | yes | yes | yes | **Alembic only** (`DATABASE_URL_MIGRATE`) — needs ownership for DDL *and* bypass for data backfills under `FORCE` |

Crucially: do **not** grant `opentroop_app` membership in `opentroop_admin` or the owner,
and do not give it `BYPASSRLS`. The app pool is a one-way door into a single tenant.

0. **Make the roles usable (one-time — migration + secrets).** The existing RLS migration
   created `opentroop_app` / `opentroop_admin` as **`NOLOGIN`**, so nothing can connect as
   them yet. A new migration/bootstrap step must make them authenticable — pick one:
   (a) `ALTER ROLE … LOGIN` with managed passwords; (b) on Cloud SQL, create IAM database
   users mapped to them (preferred in SaaS — no static passwords); or (c) add thin
   `LOGIN`+`INHERIT` login roles that are members of each. Also create/designate the
   **owner** role with schema ownership **and** `BYPASSRLS` (transfer table ownership to it
   if the bootstrap superuser differs), since migrations need both. Confirm the per-table
   `GRANT`s from migration `09a1b2c3d4e5` reach whatever role actually logs in (direct, or
   via `INHERIT` membership). Then add three settings — `database_url` (app),
   `database_url_admin`, `database_url_migrate` — provisioned as **three separate
   secrets**, never interpolated from one.
1. **Two engines / two pools** in `app/core/database.py`:
   - `engine` (default) → `settings.database_url` (`opentroop_app`); `SessionLocal` bound
     to it. Its `after_begin` issues `SET LOCAL app.current_tenant = :tid` so the policy
     has the tenant; the app-layer filter/stamp stay on. This is `DbDep`, unchanged for
     every existing route.
   - `admin_engine` → `settings.database_url_admin` (`opentroop_admin`), with a **small
     pool** (admin traffic is minimal — e.g. `pool_size=2`); `AdminSessionLocal` bound to
     it. No GUC needed (RLS is bypassed). A new `get_admin_db()` dependency yields this
     session **inside `unscoped()`** so the app-layer filter/stamp are also off (writes
     must set `tenant_id` explicitly, as the platform plane already does).
2. **Route cross-tenant paths onto `AdminDbDep`.** The platform control plane
   (`platform.py`, `provisioning.py`) and the `auth` memberships/claim cross-tenant
   lookups switch from `DbDep` to `AdminDbDep` (`Annotated[Session, Depends(get_admin_db)]`).
   The `Member.user_id == me` constraint stays in the memberships query. After this, the
   app engine is *never* used for a cross-tenant operation, and the admin engine is *only*
   used for them.
3. **Alembic on the owner role.** `alembic/env.py` connects via `DATABASE_URL_MIGRATE`
   (the owner, `BYPASSRLS`) so DDL has ownership and data backfills see all rows instead of
   fail-closing to zero. Runtime never uses this role.

Because the app-layer filter already gates on `bypass_active()`, the global `after_begin`
listener works for both engines unchanged: the admin path runs `unscoped()` (bypass on),
so it skips the GUC; the app path never bypasses, so it always stamps the GUC. No
per-transaction role switching, no ordering hazard.

Without `FORCE`, behavior is still unchanged — but dev/CI now physically segregate
`opentroop_app`, `opentroop_admin`, and the migration owner, surfacing any missing
`GRANT`, mis-routed query, or un-`AdminDbDep`'d cross-tenant path *before* enforcement.

**Self-hosted degradation:** single-tenant deployments may point all three URLs at one
owner/superuser role (RLS still installs and the app still works); the three-role split is
the SaaS posture. (Per the SaaS-first principle, optimize for the split and degrade
gracefully.)

**Exit:** the full SQLite suite and the Postgres-backed RLS tier (see
[`postgres-rls.md`](postgres-rls.md)) pass with the app engine on `opentroop_app`, the
admin engine on `opentroop_admin`, and migrations on the owner — all *before* `FORCE`
exists. A test asserts `opentroop_app` lacks `BYPASSRLS` and has no membership escalating
to it.

### Phase C — Flip enforcement

1. **New migration:** `ALTER TABLE … FORCE ROW LEVEL SECURITY` for every `TrackedBase`
   table. With `FORCE`, even the owner is subject to policy, so the boundary no longer
   depends on which role connects.
2. **Fix reproducibility while here:** replace the runtime `__subclasses__()` walk with an
   explicit, frozen table list captured in the migration, so applied revisions stay
   deterministic.
3. **Gate it:** the per-PR Postgres RLS tier must be green, including the
   policy-completeness introspection test (`relrowsecurity` + a `pg_policies` row for
   every `TrackedBase` table) and the fail-closed (empty GUC → zero rows) assertion.

**Exit:** a raw `SELECT * FROM members` under `app.current_tenant = A` returns only
tenant-A rows with no app-layer help; a mismatched-`tenant_id` write is rejected by
`WITH CHECK`; the platform plane still works via the bypass role.

---

## Migration tooling rules (permanent, post-cutover)

Autogenerate is blind to RLS (policies, roles, grants live in hand-written SQL, not
`Base.metadata`). So from Phase C onward, **every new `TrackedBase` table's migration
must also**:

1. `ENABLE` + `FORCE ROW LEVEL SECURITY`,
2. `CREATE POLICY tenant_isolation` (USING + WITH CHECK on `tenant_id`), and
3. `GRANT SELECT, INSERT, UPDATE, DELETE … TO opentroop_app, opentroop_admin`.

Provide a reusable migration helper (`rls.enable_for(table_name)`) so this is one call,
not copy-paste. The policy-completeness CI test is the backstop that fails the PR if a new
table ships without coverage. Data-only migrations that touch tenant tables run on the
Alembic/owner connection (`DATABASE_URL_MIGRATE`, `BYPASSRLS`) — otherwise they silently
affect zero rows.

---

## Deployment topology: in-process now, separate admin service later

Two separate questions hide here: a separate **DB connection** for the control plane
(decided above — yes, in Phase B) versus a separate **deployable service/process** for it.
They are independent.

**Recommendation: keep the platform control plane in-process through the RLS cutover;
split it into its own service only when you reach real multi-tenant production.**

What each boundary buys:

- The **separate admin pool** (Phase B) defeats the *likely* threat — a scoping bug
  leaking PII — because the app role cannot bypass RLS at all.
- A **separate admin process** additionally defends against a *rarer* threat — in-process
  compromise (e.g. RCE/SSRF in a tenant route reaching the live `BYPASSRLS` engine), since
  those credentials would not be loaded in the tenant-facing process. It also lets the
  console sit behind a separate domain/VPN (`admin.opentroop.app`), and scale and fail
  independently of tenant traffic.

**Trigger to split (not a date):** before the control plane is internet-exposed alongside
multiple *real* tenants' PII — i.e. at/just before public multi-tenant launch, or when the
console gains high-blast-radius powers (billing, tenant impersonation, bulk operations).
While you effectively have one tenant, a second service is pure overhead — don't.

**The seam already exists**, so the later split stays cheap: `platform.py` +
`provisioning.py` + `PlatformAdminDep` + the admin engine lift into a second FastAPI
entrypoint (e.g. `app.admin:app`) that imports the **same** `app` package and is deployed
as a separate Cloud Run service on the admin domain, holding the `opentroop_admin`
credentials. The tenant app then **drops the admin engine and stops mounting `/platform`**,
so its process contains no bypass capability at all.

Two mechanics make this work (confirmed against the current `app/main.py` /
`app/core/database.py`, which are both flat module-level assemblies today):

- **App factory.** Refactor `app/main.py`'s module-level body into a
  `create_app(*, mount_platform: bool)` factory and conditionally
  `include_router(platform.router)`. Keep `app = create_app(mount_platform=…)` as a module
  global so `uvicorn app.main:app` and existing scripts/docs are unchanged; the SaaS admin
  service adds a thin `app/admin.py` exposing a platform-only app from the same factory.
  The routers are already modular, so this is mechanical.
- **Lazy admin engine (load-bearing for the guarantee).** `database.py` creates its engine
  at **module import**. If the admin engine is added the same way, *every* process that
  imports `database.py` — including the tenant app — opens a `BYPASSRLS` pool, defeating
  the entire point of the split. So the admin engine must be created **lazily** (built on
  first use by `get_admin_db`, only in a process that has `DATABASE_URL_ADMIN` set), never
  at import. A tenant process that never calls `AdminDbDep` and has no admin URL then holds
  **zero** bypass capability. `get_admin_db` should fail loudly if the admin URL is absent.

### This must NOT complicate self-hosting

Make the split a **deployment topology, not a code fork.** A self-hoster runs one troop;
forcing them to run two services and two domains for a console they touch once is
unacceptable, and would violate the SaaS-first / degrade-gracefully principle. Therefore:

- **One codebase/package.** Whether the platform routes mount is a config flag
  (e.g. `MOUNT_PLATFORM`), never a separate build or fork.
- **Single-process all-in-one stays first-class.** Self-hosted runs one process with the
  platform routes mounted, and may point all three connection URLs at a single
  owner/superuser role. With a single tenant, the role split and even `FORCE` are SaaS
  hardening — RLS is a no-op backstop — so a self-hoster can ignore all of it. They mostly
  provision via the `provision-tenant` CLI anyway, so the console is optional for them.
- **SaaS** runs the two-service topology from the *same* code with the flag flipped and
  three distinct credentials.

Net: self-hosted complexity is **unchanged** by this plan (one process; one *or* three
URLs; optional console). The separate admin service is a SaaS-only deployment choice taken
later — it does not fork the code or burden single-tenant operators.

---

## Sequencing constraints (why now, not later)

Enforce **before** these land, because each makes RLS both more valuable and more
expensive to retrofit:

- **Mobile sync** (pull/push) — a leaked row in a sync payload *persists on-device* and
  re-uploads; the app filter doesn't cover raw/bulk sync paths. RLS must predate the first
  sync endpoint.
- **Text-to-SQL / read replica** (Pillar 5) — executes semi-arbitrary `SELECT`s; RLS is
  the only credible tenant guard there.
- **Schema growth** — retrofit cost scales with table count and accumulated data
  migrations. Cheapest at today's ~20 tables.

---

## Definition of done

- [ ] No redundant `tenant_id ==` predicates in scoped routes (Phase 0).
- [ ] Every cross-tenant access is a greppable `unscoped()` + new-`unscoped()` lint (A).
- [ ] Runtime roles are loginable (or IAM-mapped) and the owner role owns the schema +
      has `BYPASSRLS`; three credentials wired as three secrets (B.0).
- [ ] Separate app/admin engines: app traffic on `opentroop_app`, cross-tenant on
      `opentroop_admin` via `AdminDbDep`, Alembic on the owner role; app role provably
      cannot reach `BYPASSRLS` (B).
- [ ] `FORCE ROW LEVEL SECURITY` on all `TrackedBase` tables; reproducible table list (C).
- [ ] Per-PR Postgres RLS tier green, incl. policy-completeness + fail-closed tests.
- [ ] New-table RLS helper + CI guard documented in `backend/CLAUDE.md`.

---

## Rollback

Each phase is independently revertable. The Phase C flip is the only one that changes
enforcement: its `down_revision` simply `… NO FORCE ROW LEVEL SECURITY`s every table,
returning to the dormant-but-installed state. Because Phases A/B leave the bypass paths
and roles correct, reverting C is safe and instantaneous; reverting B collapses the two
runtime engines back to a single owner connection.

---

## Out of scope

- **Splitting the platform control plane into its own deployed service** — recommended
  *after* this cutover, at real multi-tenant launch; the trigger, seam, and self-hosted
  guarantees are documented under "Deployment topology" above, but the actual second
  service is a later workstream.
- The app-layer and DB-layer **designs** themselves — see
  [`tenant-data-access.md`](tenant-data-access.md) and [`postgres-rls.md`](postgres-rls.md).
- On-device multi-tenant isolation (mobile's job — see
  [`tenant-switcher.md`](tenant-switcher.md)).
- Per-row/column policies (medical-data visibility) — handled at the endpoint/RBAC layer.
