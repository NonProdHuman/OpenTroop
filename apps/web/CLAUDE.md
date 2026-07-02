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

The web app does **not** use a generated API-client package (a generated client is
planned for mobile only). Instead it uses two purpose-built layers:

- **`useApi()`** (`src/lib/api.ts`) — the central HTTP client. Wraps `fetch` with a Clerk
  `Bearer` token and the `X-Tenant-ID` header. Use this in all data hooks.
- **`src/types/api.ts`** — hand-written TypeScript mirrors of the backend Pydantic schemas.
  When you add or change a backend field, update this file to match.

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

Add the corresponding type(s) to `src/types/api.ts`.

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
