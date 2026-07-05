# 0004. Postgres RLS as tenant-isolation defense-in-depth

- **Status:** Accepted
- **Date:** 2026-07-05 (recorded retroactively; per `docs/spec/postgres-rls.md`)

## Context

In a shared multi-tenant platform (ADR 0001), the worst-case bug is
**cross-tenant data leakage** — one troop seeing or mutating another's members,
events, or advancement. Tenant scoping is enforced in the application layer:
every tenant-scoped query filters by the resolved `tenant_id`
(`app/core/deps.py`, `app/core/tenant.py`). But application-layer scoping is only
as good as its weakest query. A single handler that forgets the filter, a raw
query, a future contributor unaware of the convention, or an ORM relationship
that loads across the partition — any one leaks across tenants, and it fails
*silently* (returns data, no error).

## Decision

Enforce tenant isolation **twice**: in the application layer (the primary,
always-on path) **and** in the database via **PostgreSQL Row-Level Security**.
Every tenant-scoped table has RLS policies that constrain visibility to the
current tenant, set per-transaction from the resolved tenant context. Enabling
RLS is a **required, tested step**: every new `TrackedBase` migration must call
the shared `rls.enable_rls_for(...)` helper, and a dedicated CI job
(`backend/tests/rls/`) fails the build if a tenant-scoped table is missing its
policy. See `docs/spec/postgres-rls.md` and `docs/spec/rls-enforcement-rollout.md`.

## Consequences

- A forgotten application-layer filter degrades to "returns nothing" (RLS blocks
  it) instead of "leaks another tenant's rows." The failure mode flips from
  silent breach to visible bug.
- Every new tenant-scoped table carries an obligation: add the RLS policy in its
  migration or CI stops the PR. This is friction, and it is intentional — it's
  the point of the control.
- The database runs with a session/transaction tenant GUC set on each request;
  code paths that bypass the normal session (scripts, some background jobs) must
  set it explicitly or run as an RLS-exempt role deliberately.
- The test suite runs on SQLite (no RLS) for speed; RLS is validated by a
  separate Postgres-backed CI job. RLS is therefore *not* exercised by the bulk
  of unit tests — it's a backstop verified separately, not a substitute for the
  application-layer filter.

## Alternatives considered

- **Application-layer scoping only.** Rejected: one missed filter is a silent
  cross-tenant breach, the highest-severity bug class for this product. Too much
  rests on every query being perfect forever.
- **A database (or schema) per tenant.** Strong isolation, rejected: does not
  fit a many-small-tenants SaaS — thousands of Postgres databases/schemas,
  painful migrations and connection management, and a poor fit for the shared
  platform tier.
- **RLS as the *only* isolation.** Rejected: application-layer filtering stays
  the primary, portable enforcement (it also works for self-hosters on other
  setups); RLS is the belt to its suspenders, not a replacement.
