# 0001. SaaS-first platform, Clerk for auth

- **Status:** Accepted
- **Date:** 2026-07-05 (recorded retroactively; decision predates the log)

## Context

OpenTroop replaces TroopWebHost for Scouting units. Two deployment shapes are
possible: a hosted multi-tenant service serving many troops, or a self-hosted
single-troop instance. These pull in opposite directions — a shared platform
wants a tenant partition key, subdomain routing, per-tenant rate limiting, and a
staff control plane above the troops; a single-instance tool wants none of that
and resents the overhead.

We had to pick a **primary design target**, because "support both equally" in
practice means every feature is designed twice and the harder multi-tenant paths
(tenant isolation, a platform admin tier, billing) get deferred until they're
expensive to retrofit. Auth is the sharpest example: a hosted platform needs
managed sign-up, SSO, and per-tenant user administration that a self-hoster
would rather not run.

## Decision

**OpenTroop is built SaaS-first.** Multi-tenancy is a first-class assumption
throughout: every tenant-scoped row carries a `tenant_id`, tenants route by
subdomain, and there is a **platform (global) tier above tenants** — distinct
from tenant-scoped RBAC — that owns tenant creation, tenant-admin
administration, and billing/ops (`app/routers/platform.py`, `PlatformBase`,
`User.platform_role`).

**Auth uses Clerk** as the OIDC provider for the hosted platform. The backend
validates standard OIDC claims (`app/core/auth.py`), so any compliant provider
(Authentik, Google, Apple) works for self-hosters — but Clerk is the supported
default and the reason multi-tenant sign-up/SSO is a solved problem rather than
a build.

Self-hosting (one troop, one instance) remains a **supported secondary mode**.
Where the two conflict, we optimize for SaaS and degrade gracefully for
single-tenant.

## Consequences

- New capabilities must answer "does this row belong to one troop or to the
  platform?" — `TrackedBase` vs `PlatformBase`. Getting this wrong is a data-
  isolation bug, so it's a required review question (see ADR 0005).
- Tenant isolation is load-bearing, which justifies defense-in-depth (ADR 0004)
  and the edge-security belts (`app/core/edge_security.py`).
- Self-hosters take on their own OIDC provider config and don't get the platform
  control plane UI; the `provision-tenant` CLI is their path in.
- We depend on Clerk for the hosted product. The OIDC-standard boundary in
  `auth.py` keeps that dependency swappable rather than load-bearing in the
  domain code.

## Alternatives considered

- **Self-host-first, add SaaS later.** Rejected: retrofitting a `tenant_id`
  partition and a platform tier onto a single-tenant schema is the exact
  expensive migration we're trying to avoid.
- **Roll our own auth.** Rejected: multi-tenant sign-up, SSO, email
  verification, and session management are a large, security-sensitive surface
  with no differentiation for us.
- **A different managed auth provider (Auth0, WorkOS, Cognito).** Any OIDC
  provider fits the backend boundary; Clerk was chosen for its multi-tenant and
  Next.js ergonomics. Not re-litigated per-provider — the standard claims
  boundary makes a future switch cheap.
