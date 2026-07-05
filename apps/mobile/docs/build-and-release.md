# Building, running & releasing the mobile app (iOS & Android)

OpenTroop mobile is **one** Expo / React Native codebase that builds to both iOS
and Android from the same source — every screen, the offline mirror, and the
outbox are shared. "iOS-first" was a testing/release order, not a fork, so
standing up Android is build/release plumbing, not new features.

Cloud builds run on **EAS Build** (Expo's hosted builders); config lives in
[`eas.json`](../eas.json). The native `android/` and `ios/` folders are generated
at build time from `app.json` and are git-ignored — never commit them.

---

## 1. Prerequisites

**Everyone:**
- Node + `pnpm` (already required for the repo), run `pnpm install` at the root.
- A free **Expo account** and the EAS CLI: `npm install -g eas-cli && eas login`.

**For iOS** (dev + release): a **Mac** with **Xcode** (iOS Simulator). Publishing
needs a paid **Apple Developer Program** membership ($99/yr).

**For Android** (dev + release): **Android Studio** (SDK + an emulator) or a
physical device with USB debugging. Publishing needs a one-time **Google Play
Developer** account ($25).

You do *not* need Xcode/Android Studio to write code or run the unit tests — only
to run the app on a simulator/emulator or make local native builds. EAS can build
both platforms in the cloud regardless of your OS.

---

## 2. Run it in development

### Environment (`.env`)

```bash
cp apps/mobile/.env.example apps/mobile/.env    # git-ignored
```

Set `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` and point the app at a backend — for
local dev, `EXPO_PUBLIC_API_URL=http://localhost:8000` (see §3 for the full
picture). Then:

```bash
cd apps/mobile
pnpm start          # Expo dev server — press i (iOS sim), a (Android emulator)
```

### Expo Go vs. a development build

- **Expo Go** (the app from the store) is the fastest way to iterate and is fine
  for most screens. **Caveat:** remote **push notifications do not work in Expo
  Go** (Expo removed them in SDK 53+). Everything else — offline mirror, Face ID
  lock, secure store, SQLite — works.
- A **development build** (a custom dev client that includes our native modules)
  is what you want to exercise **push** and to test a build that behaves like a
  real install:

  ```bash
  eas build --profile development -p ios       # or -p android
  # install the resulting build on the simulator/emulator/device, then:
  pnpm start --dev-client
  ```

Do an Android run with `pnpm start` → press `a` (emulator running, or device
attached). Same JS as iOS — if it works on one it works on the other, barring the
platform-native bits (push transport, biometrics), which are covered below.

---

## 3. Which server does the app talk to? (self-hosting)

**The API URL is configured at _build time_, not at runtime.** The
`EXPO_PUBLIC_*` values are compiled into the app bundle
([`src/lib/env.ts`](../src/lib/env.ts)):

| Variable | Meaning |
|----------|---------|
| `EXPO_PUBLIC_API_URL` | **Dev / single-origin:** one base URL for everything; the app sends `X-Tenant-ID` (backend runs `ALLOW_TENANT_ID_HEADER=true`). |
| `EXPO_PUBLIC_APP_DOMAIN` | **SaaS:** tenant APIs at `https://<tenant-slug>.<domain>/api` (subdomain-only resolution; `ALLOW_TENANT_ID_HEADER=false`). |
| `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` | The auth (Clerk/OIDC) instance for that deployment. |

**What this means for self-hosting:** yes, the URL is configurable — but it is
baked in per build, so:

- **Hosted SaaS.** The app we publish to the App Store / Play Store is built with
  `EXPO_PUBLIC_APP_DOMAIN=opentroop.app` and the OpenTroop Clerk key. Every troop
  on the hosted platform uses that one published app; tenants are separated by
  their subdomain slug, not by app config.
- **A self-hosting org that wants its own app** builds its **own** app from this
  source with `EXPO_PUBLIC_APP_DOMAIN=troop-42.example.org` (or `EXPO_PUBLIC_API_URL`
  for a single-origin deployment) **and its own auth key**, then ships it under
  its own app identity (bundle id / package name in `app.json`). This is fully
  supported and matches the self-host-is-your-own-stack model
  ([ADR-0001](../../../docs/adr/0001-saas-first-clerk-auth.md)) — you already run
  your own backend and auth, and the app is one more thing you build.

> **Why not a single published app where a self-hoster just types in their server
> URL?** Because it's not only the URL — **auth is also per-deployment**. Each
> server has its own Clerk/OIDC issuer, and the publishable key is compile-time.
> A true "point one app at any server" experience needs runtime configuration of
> *both* the API base and the auth/OIDC config (a first-run "choose your server"
> flow). That's a real feature with security implications, not built today — it's
> noted as a possible future enhancement. For now, self-host = your own build.

To produce a self-host build, set that org's values as EAS environment variables
(next section) or in a local `.env`, change the `ios.bundleIdentifier` /
`android.package` in `app.json` to that org's identifiers, and build as below.

---

## 4. Publishing

### One-time per app identity

```bash
eas init      # links the project; writes extra.eas.projectId into app.json
```

Set the app-time env vars as **EAS environment variables** per profile (never
commit keys):

```bash
eas env:create --environment production --name EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY --value pk_live_…
eas env:create --environment production --name EXPO_PUBLIC_APP_DOMAIN --value opentroop.app
```

**Push credentials** (once per platform, stored server-side in Expo — nothing in
the repo):
- **iOS (APNs):** EAS provisions the APNs key on the first iOS build, or run
  `eas credentials`.
- **Android (FCM v1):** create a Firebase project, download its **service account
  JSON**, then `eas credentials` → Android → *Google Service Account* → *Push
  Notifications (FCM V1)* → upload. The Expo Push Service uses it; no
  `google-services.json` needs committing. Run the backend with `PUSH_BACKEND=expo`.

### Build profiles (`eas.json`)

| Profile | Android | iOS | Use |
|---------|---------|-----|-----|
| `development` | APK (dev client) | simulator | day-to-day dev with native modules |
| `preview` | APK (sideload) | internal | hand a test build to leaders |
| `production` | AAB (Play Store) | store | release; `autoIncrement` bumps the build number |

```bash
eas build -p ios --profile production
eas build -p android --profile production
```

### Ship to testers, then the stores

- **iOS:** `eas submit -p ios --profile production` → the build lands in **App
  Store Connect** → distribute via **TestFlight** (beta) → submit for App Store
  review.
- **Android:** `eas submit -p android --profile production` → **Play Console** →
  **Internal testing** track (fastest) → Closed/Open testing → Production. Needs a
  Play Console **service account** for `eas submit`.

---

## 5. Verifying config locally (no cloud build)

```bash
npx expo config --type public                 # validates app.json / plugins
npx expo prebuild -p android --no-install     # generates android/ from config (delete after — git-ignored)
npx expo prebuild -p ios --no-install         # same for ios/
```

---

## Known follow-ups

- **App icon & splash:** currently Expo's default icon on both platforms. When
  brand art exists, add `expo.icon`, `expo.android.adaptiveIcon` (foreground +
  `backgroundColor`), and a splash config — a launch task, not a build blocker.
- **Runtime server selection for self-hosters** (a first-run "choose your server"
  flow configuring API base + auth) — see §3. Not built; would need its own spec.
- **Store presence:** screenshots, descriptions, privacy policy, and data-safety /
  App Privacy forms live in the Play Console / App Store Connect, outside this repo.
```
