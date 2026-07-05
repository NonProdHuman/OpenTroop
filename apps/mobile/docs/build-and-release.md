# Building & releasing the mobile app (iOS & Android)

OpenTroop mobile is a single Expo / React Native codebase that builds to **both**
iOS and Android from the same source — every screen, the offline mirror, and the
outbox are shared. "iOS-first" was a testing/release order, not a fork, so
Android needs build/release plumbing, not new features.

Builds run on **EAS Build** (Expo's cloud). Config lives in
[`eas.json`](../eas.json); native projects are generated at build time from
`app.json` (the `android/` and `ios/` folders are git-ignored — do not commit
them).

## One-time setup

```bash
npm install -g eas-cli
eas login                 # Expo account
eas init                  # links the project; writes extra.eas.projectId into app.json
```

### App-time environment variables

The app reads `EXPO_PUBLIC_*` at build time (baked into the bundle). Set these as
**EAS environment variables** per profile — never commit keys:

| Variable | Purpose |
|----------|---------|
| `EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk auth |
| `EXPO_PUBLIC_APP_DOMAIN` | SaaS mode — tenant APIs at `https://<slug>.<domain>/api` |
| `EXPO_PUBLIC_API_URL` | Dev/self-host only — single origin + `X-Tenant-ID` header |

```bash
eas env:create --environment production --name EXPO_PUBLIC_CLERK_PUBLISHABLE_KEY --value pk_live_…
eas env:create --environment production --name EXPO_PUBLIC_APP_DOMAIN --value opentroop.app
```

## Build profiles (`eas.json`)

| Profile | Android | iOS | Use |
|---------|---------|-----|-----|
| `development` | APK (dev client) | simulator | day-to-day dev with a custom dev client |
| `preview` | APK (sideload) | internal | share a test build with leaders |
| `production` | AAB (Play Store) | store | release; `autoIncrement` bumps the build number |

```bash
# Android
eas build -p android --profile preview       # installable .apk
eas build -p android --profile production     # .aab for the Play Store

# iOS
eas build -p ios --profile preview
eas build -p ios --profile production
```

## Push notifications

The app registers Expo push tokens (`src/lib/push.ts`) and the backend stores
them per platform and sends via the Expo Push Service (set `PUSH_BACKEND=expo`).
Expo abstracts APNs vs FCM, but each platform needs its transport credential
configured **once, server-side in Expo** — nothing is committed to the repo:

- **iOS (APNs):** EAS manages the APNs key automatically during the first iOS
  build, or run `eas credentials` → iOS → Push Notifications.
- **Android (FCM v1):** create a Firebase project, download its **service account
  JSON**, then `eas credentials` → Android → *Google Service Account* → *Push
  Notifications (FCM V1)* and upload it. This is a server credential for the Expo
  Push Service; the Expo-push flow does **not** require committing a
  `google-services.json` into the build.

Android notifications tint with the brand color (`expo-notifications` plugin
`color` in `app.json`). On Android 13+ the OS runtime-prompts for the
notification permission the first time the app asks.

## Submitting to the stores

```bash
eas submit -p android --profile production    # needs a Play Console service account
eas submit -p ios --profile production        # needs App Store Connect access
```

## Verifying config locally (no cloud build)

```bash
npx expo config --type public                 # validates app.json / plugins
npx expo prebuild -p android --no-install     # generates android/ from config (then delete it — git-ignored)
```

## Known follow-ups

- **App icon & splash:** the app currently ships Expo's default icon on both
  platforms. When brand art exists, add `expo.icon`, `expo.android.adaptiveIcon`
  (foreground + `backgroundColor`), and a splash config — a launch task, not a
  build blocker.
- **Play Store listing:** screenshots, description, privacy policy, and data-safety
  form are handled in the Play Console, outside this repo.
