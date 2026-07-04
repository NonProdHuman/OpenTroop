# OpenTroop Mobile (Expo, iOS first)

The offline-first mobile client (GH-93; offline data-layer spec in GH-153).
M3 scaffold: Clerk sign-in, troop switcher, Events/Roster/Settings tabs reading
the live API. The SQLite mirror + offline outbox land in M4.

## Run it

```bash
pnpm install                              # from the repo root
cp apps/mobile/.env.example apps/mobile/.env   # add your Clerk publishable key
cd apps/mobile
pnpm start                                # Expo dev server → press i for iOS simulator
```

- Point `EXPO_PUBLIC_API_URL` at a running backend (`uv run uvicorn app.main:app` or
  `./start.sh`). The iOS simulator can reach `http://localhost:8000` directly; a
  physical device needs your machine's LAN IP.
- Sign in with a Clerk account that has claimed a Member (`seed-dev-data` +
  the invite/claim flow, or your existing dev account).

First run may suggest `npx expo install --fix` to align native module patch
versions with the installed SDK — safe to accept.

## Checks

```bash
pnpm --filter mobile typecheck   # tsc --noEmit
pnpm --filter mobile lint        # eslint (eslint-config-expo)
pnpm --filter mobile test:run    # vitest — pure-TS units (Node, no RN runtime)
```

## Conventions

- Types come from `@opentroop/api-types` (generated; `pnpm gen:api`) via thin
  aliases in `src/lib/types.ts` — never hand-write API shapes.
- Query keys are tenant-prefixed, mirroring the web app.
- Tenant resolution: `EXPO_PUBLIC_API_URL` set → single origin + `X-Tenant-ID`
  header (dev); otherwise `https://<slug>.<EXPO_PUBLIC_APP_DOMAIN>/api`
  (SaaS subdomain routing — works with `ALLOW_TENANT_ID_HEADER=false`).
- Keep `src/lib` free of React Native imports where possible — that's the layer
  vitest covers in Node, and where the M4 sync engine lives.
