# OpenTroop Mobile (Expo — iOS & Android)

The offline-first mobile client (GH-93; offline data-layer spec in GH-153): a
single Expo / React Native codebase that builds to both iOS and Android from the
same source. Clerk sign-in, troop switcher, Events/Roster/Advancement/Messages
tabs on a local SQLite mirror with an offline command outbox, push
notifications, Face ID app lock, and system-driven dark mode.

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

To run on Android, press `a` in the Expo dev server (Android emulator or a
connected device with Expo Go / a dev client).

## Building for release

See [`docs/build-and-release.md`](docs/build-and-release.md) for EAS build
profiles, per-platform push-credential setup (APNs / FCM), and store submission.

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
