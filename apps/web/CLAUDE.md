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
pnpm --filter @opentroop/api-client generate       # regenerate TS types from OpenAPI spec
                                                   # (requires backend running on :8000)
```

Copy `apps/web/.env.local.example` → `apps/web/.env.local` and fill in Clerk keys and
`NEXT_PUBLIC_TENANT_ID` before running. See `docs/local-setup.md` for the full walkthrough.

## Conventions

- All project tooling via `pnpm exec <tool>` — never `npx`.
- Add shadcn/ui components from `apps/web/`: `pnpm exec shadcn add <component>`.
- `src/components/ui/` is shadcn-generated — don't manually edit or write tests for those files.

## API and data fetching

The web app does **not** use the `@opentroop/api-client` package (that's intended for mobile).
Instead it uses two purpose-built layers:

- **`useApi()`** (`src/lib/api.ts`) — the central HTTP client. Wraps `fetch` with a Clerk
  `Bearer` token and the `X-Tenant-ID` header. Use this in all data hooks.
- **`src/types/api.ts`** — hand-written TypeScript mirrors of the backend Pydantic schemas.
  When you add or change a backend field, update this file to match.

All server state is managed with **TanStack React Query**. Data hooks live in
`src/hooks/use-*.ts` and use `useQuery` / `useMutation`. Query keys are plain string arrays
(`["members"]`, `["events"]`, etc.).

### Adding a new data hook

```typescript
// src/hooks/use-foo.ts
"use client"

import { useQuery } from "@tanstack/react-query"
import { useApi } from "@/lib/api"
import type { Foo } from "@/types/api"

export function useFoo() {
  const { request } = useApi()
  return useQuery({
    queryKey: ["foo"],
    queryFn: () => request<Foo[]>("/foo/"),
  })
}
```

Add the corresponding type(s) to `src/types/api.ts`.

## Route structure

App Router route groups:

| Group / path | Purpose |
|---|---|
| `(auth)` | Sign-in / sign-up pages — Clerk-handled, no sidebar |
| `(dashboard)` | Protected pages with `AppSidebar` layout |
| `platform` | Platform-admin–only pages (tenant management) |

## Testing

Tests use **Vitest + Testing Library** in a jsdom environment. Test files are co-located
with source (e.g., `foo.test.tsx` next to `foo.tsx`) — any file matching
`src/**/*.{test,spec}.{ts,tsx}` is picked up automatically.

- Setup file: `src/test/setup.ts` — extends jest-dom matchers and stubs `window.matchMedia`
  (required by shadcn's `useIsMobile`; jsdom doesn't implement it).
- `src/components/ui/` is excluded from coverage (shadcn-generated, not ours to test).
- Path alias `@/` resolves to `src/` in both app code and tests.
