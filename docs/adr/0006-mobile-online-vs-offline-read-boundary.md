# 0006. Mobile online-read vs. offline-mirror boundary

- **Status:** Accepted
- **Date:** 2026-07-05

## Context

The mobile app has two ways to read and write server data:

- **Offline, through the mirror** (ADR 0002): `use-mirror.ts` hooks read the
  local SQLite replica; writes enqueue on the command outbox and replay FIFO.
- **Online, through the network**: `use-advancement.ts` and `use-messaging.ts`
  use React Query against the authenticated client and fail soft with an offline
  message.

Both are legitimate, but **which one a given feature uses was never written
down.** A contributor adding a screen had no stated rule for which side to build
on, and no explanation for why (say) advancement isn't mirrored while attendance
is. There is also one deliberate exception to "all writes go through the outbox"
— marking an inbox message read — that reads as an inconsistency precisely
because it was undocumented. This ADR makes the boundary and its one exception
explicit.

## Decision

**A feature is mirrored offline if and only if a leader or member plausibly
needs it with no connectivity — i.e. at a camp or trailhead.** Everything else
is an online surface.

**Mirrored (offline, via `use-mirror` + outbox):** events, members and their
relationships, event participants (RSVP + attendance), and the message inbox.
These are the at-camp workflows — taking attendance, checking RSVPs, reading a
roster, reaching emergency contacts, reading announcements. They are in
`SYNC_ENTITIES` (`data/schema.ts`) and read from the mirror; their writes are
outbox commands.

**Online-only (via React Query, network required):** advancement catalog and
entry, group management, merit-badge recording, announcement compose, and tenant
settings. These are back-office / leadership workflows that happen with signal
(a Board of Review, planning a message, editing governance). Mirroring them
would add sync surface and offline-write complexity for data that isn't needed
in a dead zone. An online feature must **fail soft** — show an "needs a
connection" message, never a blank or broken screen.

**The one outbox exception — inbox read receipts.** Marking a message read
(`use-inbox.ts` `useMarkInboxRead`) writes the mirror optimistically **and**
fire-and-forget POSTs to the server, rather than enqueuing a command. Read state
is low-stakes, self-correcting (the next pull reconciles it), and not worth a
durable, replayable, ordered command. This is the deliberate exception to
"mutations go through the outbox"; no other write may bypass the outbox without
its own amendment to this ADR.

## Consequences

- The rule for new screens is now one sentence: *needed offline at camp → mirror
  it; otherwise → online with a soft-fail path.*
- Promoting an online feature to offline later is a real change (add it to
  `SYNC_ENTITIES`, define its commands, handle overlay) — expected and fine, but
  a decision, not an accident.
- The read-receipt bypass is a known, bounded carve-out, not drift. A reviewer
  seeing a direct-write-plus-POST there can check it against this record instead
  of "fixing" it.
- The seam is enforced only by convention and code review; nothing mechanical
  stops someone from putting an at-camp feature online. Keep this ADR the
  reference when that judgment call comes up.

## Alternatives considered

- **Mirror everything.** Rejected: every online-only feature (advancement,
  compose, settings) would need sync entities and offline-write commands for
  data no one needs without signal — cost with no at-camp payoff.
- **Mirror nothing / online-only app.** Rejected by ADR 0002 — fails the core
  use case.
- **Route inbox read receipts through the outbox for consistency.** Rejected:
  durable ordered replay is overkill for self-correcting read state; the
  optimistic-write-plus-best-effort-POST is simpler and adequate. Documented here
  rather than "corrected."
