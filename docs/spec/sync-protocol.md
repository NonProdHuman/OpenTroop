# Offline Sync Protocol Spec

**Status:** Accepted — skeletal pull endpoint implemented for Member
**Pillar:** cross-cutting (the offline-first contract for Pillars 1–4)
**Related:** [`tenant-data-access.md`](tenant-data-access.md) · [`twh-sync.md`](twh-sync.md) ·
GitHub #120 (this spec) · #93 / #106 (mobile consumers) · #115 (index shape) · #121 (retention)

---

## Overview

Offline-first background sync is the product's reason for existing: leaders must be able
to work at camps without connectivity. The schema groundwork has been in place since day
one — client-generatable UUIDv7 PKs, `updated_at`, `is_deleted` tombstones, `tenant_id`
on every row — but nothing specified the wire protocol. This spec decides it, because
every API surface shipped before this decision inherits its constraints.

The design in one paragraph: clients **pull** changed rows (including tombstones) per
entity with keyset pagination over a **server-assigned monotonic sync cursor**, and
**push** batches of client-generated-UUID upserts that the server validates row-by-row,
applying **last-writer-wins on `updated_at`** for member-editable fields and
**server-authoritative** semantics for everything permission- or workflow-derived.
Permissions are never enforced client-side; the client caches its last-known permission
set for UI affordances only, and every pushed row is re-authorized on the server.

## Decision 1 — Cursor: a dedicated monotonic `sync_seq`, not `updated_at`

Every syncable table carries a `sync_seq BIGINT NOT NULL` assigned from a single global
Postgres sequence (`sync_seq`) on **every insert and update** (including soft-deletes,
which are updates). Clients page with `WHERE (sync_seq, id) > (:since_seq, :since_id)
ORDER BY sync_seq, id`.

Why not an `updated_at` high-water mark:

- **Ties and skew.** `updated_at` has microsecond ties under bulk writes (the TWH
  importer stamps thousands of rows in one transaction) and is sourced from app-server
  clocks, which can regress. Correct paging then needs `(updated_at, id)` keyset *plus*
  an overlap re-read window — more client complexity, forever.
- **A sequence is exact.** `nextval` is strictly monotonic per value drawn; `(sync_seq,
  id)` keyset paging never skips and never duplicates (the `id` tiebreak makes the
  ordering total even if a backfill or non-Postgres dev DB produces duplicate seq
  values).
- `updated_at` keeps its job as the **conflict signal** (Decision 4); the cursor and the
  conflict clock are deliberately different columns with different guarantees.

**Transaction-visibility caveat (accepted, mitigated):** a long-running transaction can
commit rows with *lower* `sync_seq` than values a client has already paged past. This is
inherent to any commit-time-invisible counter (including `updated_at`). Mitigation: all
current write paths are short request-scoped transactions, and the one long writer (the
TWH importer) runs before a tenant's clients ever sync. If bulk background writers appear
later, the pull endpoint gains a *stability horizon* (exclude rows younger than N
seconds) — noted here so the fix is designed, not rediscovered.

**Adoption pattern:** a `Syncable` mixin (`app/models/base.py`) supplies the column; each
adopting table adds a `(tenant_id, sync_seq)` index and a backfill migration. `Member`
adopts now (the skeleton); remaining entities adopt when their pull endpoints are built,
in dependency order (members → relationships/groups → events → participants).

On SQLite (tests and quick local dev) there is no sequence; `sync_seq` falls back to
`MAX(sync_seq)+1` per statement. Duplicate values under concurrency would be possible
there, but SQLite deployments are single-writer test environments, and the `id` tiebreak
keeps paging correct regardless.

## Decision 2 — Pull: per-entity endpoints under `/sync/*`

`GET /sync/members?since_seq=0&since_id=&limit=500` (and later `/sync/events`, …), each
gated by that entity's read permission, returning:

```jsonc
{
  "items": [ /* full entity Read schema, including is_deleted */ ],
  "next_since_seq": 41,     // cursor of the last row returned (echo back verbatim)
  "next_since_id": "0198…", // id tiebreak of the last row returned
  "has_more": true
}
```

- **Tombstones are delivered**: rows with `is_deleted: true` appear in the stream so the
  client can delete locally. This is the one read path that bypasses the automatic
  soft-delete filter (via the greppable `include_deleted()` scope).
- **Tenant scoping is automatic** (ContextVar + RLS backstop, per
  `tenant-data-access.md`); the endpoint adds no tenant predicate by hand.
- **Initial sync** is the same call with `since_seq=0` — no separate bootstrap endpoint.
- Per-entity (not one unified feed) because visibility rules are per-entity: events must
  be filtered by audience (`visibility_clause`), members by roster readability. A unified
  heterogeneous feed would centralize every entity's authorization in one endpoint —
  rejected. The cost is that cross-entity consistency is eventual (a client may briefly
  hold a `GroupMember` whose `Group` hasn't arrived); clients must tolerate dangling
  references until the next pull round completes. UUIDv7 FKs make this safe to store.
- **Visibility-revocation caveat:** when a row leaves a client's *visibility* without
  being deleted (an event's audience narrows), no tombstone exists to deliver. Accepted
  for now: audience changes bump the event's `sync_seq`, the row re-syncs, and a client
  that can no longer read it gets it filtered out — so a periodic **full-refetch
  reconciliation** (client walks from `since_seq=0` in the background, e.g. weekly or on
  demand) is the documented recovery mechanism for both this and any missed-tombstone
  case (Decision 5).

## Decision 3 — Push: idempotent batched upserts, per-row status

`POST /sync/{entity}` with a batch (max 500) of rows carrying client-generated UUIDv7
`id`s and a client-generated `mutation_id` (UUID) per row:

```jsonc
{ "rows": [ { "mutation_id": "…", "data": { "id": "…", "first_name": "…", … } } ] }
```

Response mirrors the batch with per-row status — the whole batch never fails atomically:

```jsonc
{ "results": [ { "mutation_id": "…", "status": "applied" | "stale" | "forbidden" | "invalid",
                 "row": { /* server state after the decision — the client reconciles to this */ } } ] }
```

- **Idempotency**: an insert whose `id` already exists is treated as an update; replaying
  a batch after a dropped response is safe because LWW comparison (Decision 4) makes
  re-application a no-op. `mutation_id` exists for client-side bookkeeping and log
  correlation, not server dedup state.
- **Authorization per row**, server-side, using the same rules as the interactive API
  (e.g. the member self/family field allowlist in `PATCH /members/{id}`): a row the
  caller may not write returns `forbidden` with the authoritative server row, and the
  client rolls its local copy back to it.
- Push endpoints are **not** part of the skeleton; they land with the first mobile
  write surface. This spec fixes their shape so the pull side and client storage are
  built compatibly.

## Decision 4 — Conflict policy: LWW by `updated_at`, with server-authoritative carve-outs

For a pushed update, the server compares the incoming row's `updated_at` (stamped by the
client at local-edit time) against the current server `updated_at`:

- **incoming newer** → apply writable fields, assign fresh `sync_seq`, status `applied`.
- **incoming older/equal** → do not write; status `stale`, server row returned. The
  client overwrites its local copy (its edit is lost — see below).

Field-level merge is **rejected**: it doubles schema complexity (per-field timestamps or
vector clocks) for a user base whose concurrent-edit collisions are rare (a troop has a
handful of editors) and whose fields are mostly independent scalars where whole-row LWW
loses at most one small edit. The failure mode is acceptable; the complexity is not.

Entity buckets (must be maintained as entities adopt sync):

| Bucket | Entities / fields | Policy |
|---|---|---|
| **LWW-safe** | Member contact/medical/OA fields, Location, free-text event fields, RSVP `rsvp_status`/`comment`/`driver`/`seat_count` (writer = the member themself or family) | last-writer-wins |
| **Server-authoritative** | everything RBAC (`Position`, `FunctionalRole`, assignments), `EventParticipant.attended` (gated on `attendance_taken`), permission-slip signature fields, `Group` rules, `Tenant` anything | reject offline writes (`forbidden`) or accept only via the interactive API online |
| **Append-only** | new rows with client UUIDv7 ids (a new RSVP, a new member created offline by a leader) | insert; duplicate-id replay is idempotent |

Client-clock skew: a client with a fast clock wins conflicts it shouldn't. Accepted for
LWW-safe fields (same trust level as the data itself — the writer is authorized to set
those fields to any value anyway). `updated_at` from clients is clamped server-side to
`now()` when it is in the future by more than 5 minutes, so a broken clock cannot
permanently shadow a row against other writers.

## Decision 5 — Tombstone retention: 180-day floor

Soft-deleted rows must remain queryable (and keep their `sync_seq` bumping on any
revival) for **at least 180 days** after deletion. A client that hasn't synced within the
window cannot converge incrementally and must full-refetch (walk from `since_seq=0`,
replacing local state) — the same reconciliation path as Decision 2's visibility caveat,
so it costs no extra client code. The future hard-delete/retention pipeline (#121) must
respect this floor and, when it purges, record a per-tenant `purged_through_seq`
watermark so the pull endpoint can tell a too-stale client to full-refetch instead of
silently under-delivering tombstones.

## Decision 6 — Permissions offline

`resolve_permissions` is server-side and stays there. The client caches the permission
set from `GET /auth/session` at last sync and uses it **only** to shape UI (hide buttons
it expects to fail). Every offline-queued write is re-authorized at push time; `forbidden`
results roll the local row back. Nothing about sync weakens the tenant boundary: pull and
push run inside the same ContextVar scoping + RLS backstop as every other request, and
the client's local SQLite mirror is partitioned by tenant (one database file per tenant —
see #153 for the client-side design).

## Skeleton shipped with this spec

- `Syncable` mixin (`app/models/base.py`), adopted by `Member`; Postgres `sync_seq`
  sequence + `(tenant_id, sync_seq)` index + backfill migration.
- `GET /sync/members` (`app/routers/sync.py`) behind `require(Permission.MEMBER_READ)`:
  keyset paging per Decision 2, tombstone delivery, `SyncMembersPage` schema.
- Tests: paging across page boundaries without skip/duplicate, update-moves-row-to-end,
  tombstone delivery, seq-tie ordering stability, tenant isolation.

## Out of scope here

Push implementation; entities beyond Member; the client-side SQLite mirror and queue
(#153); delta/field-level payload compression; server-sent notification of new changes
(clients poll — push notification integration is #82's problem).
