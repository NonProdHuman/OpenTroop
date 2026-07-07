# 0012. Anonymous read-only principal for the public demo

- **Status:** Accepted
- **Date:** 2026-07-07

## Context

We want a public demo of OpenTroop that a prospective troop can click through
without signing up — `demo.opentroop.dev` today, mirrored to `opentroop.app` when a
prod environment exists (GH-246). Two properties are non-negotiable:

1. **Read-only for the public.** Anonymous visitors must see a realistic troop
   (roster, events, groups, photos) but must never be able to mutate it, and one
   visitor must never be able to affect another's view.
2. **Zero blast radius for every other tenant.** OpenTroop is SaaS-first: the same
   binary serves many paying troops plus self-hosters. A demo affordance must be
   provably inert for all of them — a config mistake on the demo must not weaken auth
   anywhere else.

The whole product is otherwise authenticated: every tenant-scoped route resolves the
caller's `Member` from a validated OIDC token (`get_current_user` → 401 when absent).
A public demo has no token. The question is how to admit an unauthenticated reader on
exactly one tenant without punching a hole in that model.

A separate, private, Clerk-login **demo-edit** tenant covers the "let me actually
click Save" experience; it is reset nightly (see below) and is out of scope for the
anonymous carve-out — it uses ordinary auth.

## Decision

Introduce an **inert-by-default, single-tenant, structurally read-only anonymous
principal**, gated on one setting.

- **One switch, off by default.** `DEMO_TENANT_SLUG` (empty ⇒ feature entirely off).
  Nothing about request handling changes until it names a real tenant. `DEMO_VIEWER_EMAIL`
  names the seeded principal.
- **One seam.** A new `get_optional_current_user` returns `None` (instead of 401) when
  *no* bearer token is present; a bad/expired token still 401s. Only the member-context
  dependencies (`require`, `get_current_member`, `get_member_with_permissions` via
  `_resolve_current_member` in `app/core/deps.py`) consume it. `get_current_user` is
  unchanged, so `/platform/*`, `/auth/*`, and every other token-gated surface still 401
  for anonymous callers.
- **Keyed on both slug and resolved tenant id.** The anonymous principal resolves only
  when the request's *resolved* tenant is the tenant whose `slug == DEMO_TENANT_SLUG`
  (and it isn't suspended/deleted). It maps to a fixed, unclaimed (`user_id` null)
  "Demo Viewer" member seeded in that tenant. No other tenant can ever hit this path.
- **Structural read-only, independent of RBAC.** For the anonymous principal, any HTTP
  method other than GET/HEAD/OPTIONS is refused **403 in the dependency, before the
  handler runs** — regardless of what permissions the viewer resolves to. A seeding
  mistake that handed the viewer write roles still cannot mutate. Belt-and-suspenders,
  the seeded `viewer` position maps only to read-only bundles (`member-viewers`,
  `event-viewers`, `advancement-viewers`, `photo-viewers` — the last grants `photo:read`
  without `photo:upload`) and never to administrators.
- **Fair rate limiting.** Requests to the demo tenant bill a per-IP bucket (like
  `/calendar/*`) instead of the shared per-tenant bucket, so one noisy visitor can't
  429 the demo for everyone.
- **Web mirror.** On `NEXT_PUBLIC_DEMO_HOST` the middleware skips `auth.protect()` for
  tenant routes so signed-out visitors render the dashboard; the API client sends no
  Authorization header when there's no Clerk session; a site-wide banner states the
  demo is read-only and resets are fake.
- **Nightly reset of the demo-edit tenant** via a Terraform-provisioned Cloud Run Job +
  Cloud Scheduler running `seed-dev-data --reset`, opt-in behind `demo_edit_reset_enabled`.

## Consequences

- The public demo is anonymous, needs no shared password to leak, and cannot be
  vandalized: writes are refused at the auth layer, not merely hidden in the UI.
- The carve-out is auditable in one function and one setting. With `DEMO_TENANT_SLUG`
  unset, a regression test asserts anonymous requests still 401 exactly as before —
  prod and self-host are provably unaffected.
- **Cost:** a genuine (if narrow) unauthenticated read path now exists in a
  multi-tenant auth system. That is why it is single-tenant-scoped, structurally
  read-only, off by default, and shipped with a security review. The demo tenant's data
  must be treated as public — only synthetic/seed data belongs there.
- Member-context dependencies now depend on `get_optional_current_user`; any test
  helper that builds an authenticated client must override it too (done for the shared
  `_client_for` and conftest helpers).
- `seed-dev-data` seeds one extra adult (the Demo Viewer) on the demo tenant; the e2e
  manifest counts are dynamic and self-correct.

## Alternatives considered

- **A public shared login (one demo username/password).** Credentials leak, grief the
  demo, and a shared session is still a *write*-capable session — exactly what we don't
  want. Rejected.
- **Public edit with frequent resets (anonymous writes to the demo tenant).** One
  visitor's edits/deletes corrupt everyone else's view between resets, and it normalizes
  an anonymous write path. Rejected; edit access lives on the private, reset demo-edit
  tenant behind normal auth instead.
- **RBAC-only read-only (rely on the viewer holding no write permissions).** A single
  seeding or role-mapping mistake would silently grant writes. The structural method
  gate makes read-only true independent of RBAC. Kept RBAC viewer-only anyway as a
  second layer.
- **Inject the anonymous principal at `get_current_user` (user level).** That
  dependency is also used by tenant-less `/platform/*` routes, so making it
  tenant-aware would break them and widen the blast radius. The member-context seam is
  the tightest correct place.
