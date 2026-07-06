# Architecture Decision Records

An **ADR** captures one architecturally significant decision: the context that
forced a choice, the choice itself, and the consequences we accept. ADRs explain
*why the system is shaped the way it is* — the question a new contributor can't
answer from the code alone.

## ADRs vs. specs

- **`docs/spec/`** describes *what a feature does* and *what the current rules
  are*. Specs are living documents; they change as the feature changes.
- **`docs/adr/`** records *why we made a load-bearing, expensive-to-reverse
  decision* and *what we rejected*. ADRs are append-only: once **Accepted** an
  ADR is immutable. To change a decision, write a new ADR that supersedes it and
  flip the old one to **Superseded** with a link forward.

If you find yourself explaining a "why" in a code review, a CLAUDE.md aside, or a
closed issue, it probably belongs here.

## Log

| # | Title | Status |
|---|-------|--------|
| [0001](0001-saas-first-clerk-auth.md) | SaaS-first platform, Clerk for auth | Accepted |
| [0002](0002-offline-mirror-command-outbox.md) | Offline mobile: local mirror + command outbox | Accepted |
| [0003](0003-expo-react-native.md) | Expo / React Native for the mobile app | Accepted |
| [0004](0004-postgres-rls-defense-in-depth.md) | Postgres RLS as tenant-isolation defense-in-depth | Accepted |
| [0005](0005-uuidv7-tracked-base-schema-contract.md) | UUIDv7 keys and the `TrackedBase` / `PlatformBase` / `Syncable` contract | Accepted |
| [0006](0006-mobile-online-vs-offline-read-boundary.md) | Mobile online-read vs. offline-mirror boundary | Accepted |
| [0007](0007-httpx2-http-client.md) | `httpx2` as the backend HTTP client | Accepted |
| [0008](0008-navigation-sidebar-primary-ia.md) | Navigation IA: sidebar is the complete map; tabs are within-page conveniences | Accepted |

> ADRs 0001–0005 record decisions that were already in force when the log was
> created (2026-07); their content is reconstructed from the code and specs that
> implement them. 0006 documents a boundary that was implicit until now.

## Writing a new one

1. Copy [`0000-template.md`](0000-template.md) to `NNNN-short-title.md` (next
   number, zero-padded).
2. Fill it in. Keep it to roughly a page — decision records, not essays.
3. Add a row to the log table above.
4. Open the PR against `develop` like any other change.
