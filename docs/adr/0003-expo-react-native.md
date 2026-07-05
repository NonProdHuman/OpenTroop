# 0003. Expo / React Native for the mobile app

- **Status:** Accepted
- **Date:** 2026-07-05 (recorded retroactively; Mobile v1 M0 decision)

## Context

Phase 1 needs a mobile app, iOS first. The web app is already Next.js +
TypeScript + React with a generated API-types package (`@opentroop/api-types`).
We want the most code and skill sharing possible with that stack, while still
getting first-class access to the native capabilities this product needs: push
notifications, biometric app lock (Face ID), secure storage for tokens, and an
embedded SQLite database for the offline mirror (ADR 0002). We're a small team;
maintaining a second language and a parallel native toolchain is a cost we'd
rather not pay.

## Decision

Build the mobile app with **Expo (React Native)**, TypeScript, and
`expo-router` (`apps/mobile/`, GH-93). Native capabilities come from the Expo
module ecosystem: `expo-notifications` (push), `expo-local-authentication` (Face
ID / biometric lock), `expo-secure-store` (tokens, tenant list), and
`expo-sqlite` (the offline mirror on device, with a `node:sqlite` seam for
tests). Auth reuses Clerk via `@clerk/clerk-expo` (consistent with ADR 0001).
The app consumes the **same generated `@opentroop/api-types`** the web app does,
so backend contract changes surface as type errors in both clients.

## Consequences

- One language (TypeScript), one UI paradigm (React), one shared API-types
  package across web and mobile — the intended code/skill sharing.
- Expo's managed workflow gives OTA-friendly builds and a maintained native
  module set, so we don't hand-maintain Xcode/Gradle native code for the
  capabilities above.
- We accept a dependency on Expo's release cadence and module coverage. If a
  future need falls outside the ecosystem, Expo's config plugins / prebuild are
  the escape hatch before dropping to bare React Native.
- Business logic (data layer, hooks) is portable React/TS; only the view layer
  is RN-specific. Screens are styled with RN inline styles against shared tokens
  (`src/lib/theme.ts`) rather than Tailwind — the one place web and mobile
  deliberately diverge.
- iOS-first does not preclude Android: RN/Expo targets both, so Android is a
  later build target, not a rewrite.

## Alternatives considered

- **Native SwiftUI (iOS) + later Kotlin (Android).** Best native fidelity,
  rejected: two codebases in two languages, zero sharing with the web stack, and
  more surface than a small team should own for a CRUD-plus-offline app.
- **Flutter.** Strong single-codebase story, rejected: Dart shares nothing with
  our TypeScript/React investment or the generated API types.
- **Bare React Native (no Expo).** Rejected for v1: we'd hand-wire the exact
  native modules Expo already maintains (push, biometrics, secure store,
  sqlite). Expo's escape hatches mean we can drop down later if needed.
- **A PWA / responsive web app.** Rejected: weaker push, biometric, and
  background-storage guarantees on iOS, which are core to this product.
