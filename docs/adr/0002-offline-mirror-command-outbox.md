# 0002. Offline mobile: local mirror + command outbox

- **Status:** Accepted
- **Date:** 2026-07-05 (recorded retroactively; implemented per GH-153)

## Context

Scout leaders do the work OpenTroop is for — taking attendance, checking RSVPs,
recording advancement — at camps and trailheads with no connectivity. An app
that needs a live connection to read a roster or check someone in is useless
exactly when it matters most. So the mobile client must **read and write
offline**, and reconcile when signal returns, without losing or corrupting
either the user's intent or the server's state.

This is a hard, well-trodden problem (last-write-wins vs CRDTs, conflict
resolution, partial syncs, tombstones). The risk is either under-building
(a fragile cache that shows stale or empty data) or over-building (a general
sync engine we don't need).

## Decision

The mobile app is an **offline-first replica** with two cooperating halves
(`apps/mobile/src/data/`, spec: `docs/spec/sync-protocol.md`, GH-153):

1. **A local per-tenant mirror** — one SQLite file per tenant, rows stored as
   JSON documents with extracted cursor columns. It is a *replica, not a system
   of record*: every screen reads the mirror, the network is never on the read
   path. A server-assigned monotonic `sync_seq` cursor drives keyset-paged
   pulls; each page is applied **atomically with its cursor advance**
   (`applyPullPage`), so a killed app resumes at the exact page boundary. A
   periodic **mark-and-sweep full refetch** (`fullRefetch`, epoch counter)
   reconciles missed tombstones and lost visibility without ever showing an
   empty database.

2. **A command outbox** — writes enqueue typed commands replayed **strictly
   FIFO** through the *existing interactive API* when connectivity returns
   (`commands.ts`). Every server-side check (permission, attendance gate, signup
   window) runs at replay time exactly as if the user were online — the client
   never re-implements authorization. Commands coalesce per `(kind, target)` in
   their original queue position; a read overlay folds pending effects on top of
   mirror reads so offline changes show instantly (`overlay.ts`); terminal 4xx
   surface on a "Sync Issues" screen rather than silently reverting.

Because writes replay through the normal API, there is **no separate write path
or conflict-resolution engine** — the server stays the single arbiter.

## Consequences

- Reads are always instant and offline; the network only ever pulls the mirror
  forward or drains the outbox.
- Authorization is never duplicated client-side, which is the property that
  keeps an offline app from becoming a security hole.
- Additive server fields need **no local migration** — the mirror stores whole
  documents. Local migrations are limited to index/column changes.
- The cost is real complexity in `data/` (epochs, cursors, coalescing, replay
  semantics). It is contained to that directory, covered by unit tests with a
  `node:sqlite` test seam, and documented — but it is the most intricate code in
  the repo and should be changed carefully.
- Conflict handling is last-writer-at-replay, not CRDT. Adequate for
  single-editor-per-record workflows (attendance, a scout's own RSVP); a future
  multi-editor field would need its own ADR.

## Alternatives considered

- **Online-only mobile.** Rejected outright — fails the core at-camp use case.
- **React Query cache persistence as the offline story.** Rejected: gives
  offline *reads* but no durable, ordered, replayable *writes*; attendance taken
  in a dead zone would be lost.
- **A turnkey sync engine (WatermelonDB, PowerSync, Replicache, ElectricSQL).**
  Rejected for v1: each imposes its own schema/model or backend, and our
  replay-through-the-real-API approach reuses the authorization we already have.
  Revisit if the hand-rolled layer's maintenance cost outgrows its fit.
