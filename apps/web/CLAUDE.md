# Web app

Next.js 16 (App Router) + Tailwind 4 + shadcn/ui (`base-nova` style) + Clerk auth.
All commands run from the repo root unless noted.

## Commands

```bash
pnpm install                                       # install all workspace deps
pnpm dev                                           # start web app on :3000
pnpm --filter web dev                              # same, explicit
pnpm --filter web test                             # run tests in watch mode
pnpm --filter web test:run                         # run tests once (CI mode)
pnpm --filter web test:coverage                    # run tests + coverage report
```

Copy `apps/web/.env.local.example` → `apps/web/.env.local` and fill in Clerk keys and
`NEXT_PUBLIC_TENANT_ID` before running. See `docs/local-setup.md` for the full walkthrough.

## Conventions

- All project tooling via `pnpm exec <tool>` — never `npx`.
- Add shadcn/ui components from `apps/web/`: `pnpm exec shadcn add <component>`.
- `src/components/ui/` is shadcn-generated — don't manually edit or write tests for those files.

## API and data fetching

The web app does **not** use a generated API-client package (the generated
`@opentroop/api-types` package in `packages/` serves the mobile app; the web app keeps
its own generated copy for import-path stability). Instead it uses two purpose-built layers:

- **`useApi()`** (`src/lib/api.ts`) — the central HTTP client. Wraps `fetch` with a Clerk
  `Bearer` token and the `X-Tenant-ID` header. Use this in all data hooks.
- **`src/types/api.ts`** — thin aliases into `src/types/api.generated.ts`, which is
  **generated** from the backend OpenAPI spec by `pnpm gen:api` (root script → `scripts/gen-api.sh`).
  Never hand-write shapes here. When a backend field changes, run `pnpm gen:api` and commit
  the regenerated `api.generated.ts`; the generated file is the source of truth and CI fails
  on drift (the `api-types` job regenerates and diffs it). `api.ts` only maps the
  frontend-facing names (`Member`, `Event`, …) onto the backend schema components
  (`MemberRead`, `EventRead`, …).

All server state is managed with **TanStack React Query**. Data hooks live in
`src/hooks/use-*.ts` and use `useQuery` / `useMutation`. Query keys are **prefixed with
the active tenant id** (`[activeTenantId, "members"]`, `[activeTenantId, "events", id]`)
so switching tenants can never serve another tenant's cached data, and queries set
`enabled: Boolean(activeTenantId)` so nothing fires before the tenant is resolved.

### Adding a new data hook

```typescript
// src/hooks/use-foo.ts
"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import { useActiveTenant } from "@/lib/tenant-context"
import type { Foo } from "@/types/api"

export function useFoo() {
  const { request } = useApi()
  const { activeTenantId } = useActiveTenant()
  return useQuery({
    queryKey: [activeTenantId, "foo"],
    queryFn: () => request<Foo[]>("/foo"),
    enabled: Boolean(activeTenantId),
  })
}
```

If the hook needs a backend shape that isn't aliased yet, run `pnpm gen:api` to refresh
`api.generated.ts`, then add a one-line alias in `src/types/api.ts`
(e.g. `export type Foo = Schemas["FooRead"]`) — never hand-write the shape.

> **No trailing slash on collection paths.** Backend collection routes are declared
> at `""` (canonical `/foo`, not `/foo/`). Requesting `/foo/` makes the backend
> 307-redirect to `/foo`, and because `/api/*` is proxied to a *cross-origin* backend
> origin, the browser drops the `Authorization` header on that redirect → 401 / empty
> lists. Always call the no-slash path. See commit 6e6dee5 and issue #97.

## Route structure

App Router paths (the middleware in `proxy.ts` maps logical domains onto these):

| Group / path | Purpose |
|---|---|
| `(auth)` | Sign-in / sign-up pages — Clerk-handled, no sidebar |
| `landing` | Public landing page (root domain) |
| `tenant/(dashboard)` | Protected tenant pages with `AppSidebar` layout (tenant subdomains) |
| `admin` | Platform-admin–only control plane (`admin` subdomain) |
| `claim` | Invite/claim flow — links a signed-in user to their Member row |

## Testing

Tests use **Vitest + Testing Library** in a jsdom environment. Test files are co-located
with source (e.g., `foo.test.tsx` next to `foo.tsx`) — any file matching
`src/**/*.{test,spec}.{ts,tsx}` is picked up automatically.

- Setup file: `src/test/setup.ts` — extends jest-dom matchers and stubs `window.matchMedia`
  (required by shadcn's `useIsMobile`; jsdom doesn't implement it).
- `src/components/ui/` is excluded from coverage (shadcn-generated, not ours to test).
- Path alias `@/` resolves to `src/` in both app code and tests.

## E2E smoke tests (Playwright)

`apps/web/e2e/` holds a small Playwright suite (GH-171, expanded in GH-245) — a
verification loop, not a coverage suite. It runs against an **already-running**
local stack with the deterministic demo tenant seeded:

```bash
./start.sh                          # stack up (Postgres + backend + web)
scripts/e2e-seed-and-run.sh         # re-seed (+ emit manifest) and run e2e
scripts/e2e-seed-and-run.sh --ui    # same, Playwright UI mode
```

Auth uses Clerk Testing Tokens (`@clerk/testing`): `e2e/global.setup.ts` signs in
once with `E2E_CLERK_USER_EMAIL` / `E2E_CLERK_USER_PASSWORD` (password-strategy
test user in the Clerk dev instance; same email as `seed-dev-data --email`) and
persists storage state for all specs. Base URL defaults to the demo tenant's
subdomain (`http://demo.localhost:3000`); override with `E2E_BASE_URL`.

**Seed manifest is the source of truth (GH-245).** Specs never hard-code
member/event names — they import from `e2e/fixtures/seed-manifest.ts`, which reads
`e2e/.seed-manifest.json` (gitignored). That JSON is produced by the seeder
(`seed-dev-data --emit-manifest <path>`, which `scripts/e2e-seed-and-run.sh` runs
for you), so assertions can't silently drift from the seeded data. Add a field to
`build_manifest` (backend) + the `SeedManifest` interface (web) rather than
inlining a new string. A backend test (`tests/test_seed_dev_data.py`) asserts every
named row in the manifest is actually seeded, so a rename fails CI loudly.

**Stable selectors.** Prefer `data-testid` on our own components over asserting
visible text or Tailwind classes (e.g. the RSVP control exposes
`data-testid="rsvp-going"` + `data-selected`). `src/components/ui/`
(shadcn-generated) stays untouched.

**CI.** `.github/workflows/e2e.yml` stands up the full stack, seeds, and runs the
suite — gated on the Clerk `E2E_*` repository secrets, so it **skips** (never
fails) until they're wired. See the workflow header for the required secret list.
