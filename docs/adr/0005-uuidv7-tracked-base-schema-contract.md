# 0005. UUIDv7 keys and the `TrackedBase` / `PlatformBase` / `Syncable` contract

- **Status:** Accepted
- **Date:** 2026-07-05 (recorded retroactively; per `app/models/base.py`)

## Context

Two cross-cutting requirements shape every table in the schema:

1. **Offline clients generate rows** (ADR 0002). A client with no connectivity
   must be able to create a member or an RSVP and assign its primary key
   *locally*, without a round-trip to a sequence generator, and have that key be
   globally unique when it later syncs.
2. **Multi-tenant SaaS** (ADR 0001) needs a consistent tenant partition,
   soft-delete (records like alumni stay visible to leaders while tombstoned
   ones drop out of sync), conflict-signal timestamps, and — for tables the sync
   API exposes — a monotonic cursor.

Left to per-table choices, these would be implemented inconsistently, and the
"which base class / which mixin" question would be answered ad hoc, which for
`tenant_id` is a data-isolation risk.

## Decision

Encode the requirements as **shared base classes and mixins** (`app/models/base.py`),
and make picking the right one a required review question:

- **`TrackedBase`** — every tenant-scoped table. Supplies `id` (**UUIDv7** via
  `uuid6.uuid7` — client-generatable offline, time-ordered for index locality;
  never sequential integer PKs), `tenant_id` (UUID partition key), auto-managed
  `created_at` / `updated_at`, and `is_deleted` (soft-delete tombstone).
- **`PlatformBase`** — cross-tenant platform entities (`Tenant`, `User`,
  `Identity`). Same `id` / timestamps / `is_deleted`, but **no `tenant_id`**.
- **`Syncable`** (mixin) — tables the pull-sync API exposes. Adds `sync_seq`, a
  server-assigned strictly-monotonic cursor, and requires a `(tenant_id,
  sync_seq)` index.
- **`SourceTracked`** (mixin) — rows a bulk import creates. Adds nullable
  `source_system` / `source_id` / `source_updated_at` provenance for future
  incremental sync.

The dialect-agnostic SQLAlchemy `Uuid` type lets these Postgres-targeted models
run unmodified on SQLite, which is how the test suite stays DB-free.

## Consequences

- "Does this row belong to one troop or to the platform?" has a single, visible
  answer (`TrackedBase` vs `PlatformBase`) enforced in review and, for
  `tenant_id`, backstopped by RLS (ADR 0004).
- Offline row creation is a schema-level guarantee, not per-feature plumbing.
- Adopting sync for a table is a deliberate, uniform step (`Syncable` + the
  required index), not a bespoke cursor per endpoint.
- UUIDv7 keys are larger than integers and expose creation-time ordering; we
  accept both for the offline-generation and index-locality wins.
- Soft-delete means `is_deleted` must be honored everywhere; a query that
  forgets it shows tombstoned rows. This is a standing convention, not enforced
  by the type system.

## Alternatives considered

- **Sequential integer PKs.** Rejected: cannot be generated offline without
  coordination, and leak row counts.
- **Random UUIDv4.** Rejected: offline-generatable but not time-ordered, causing
  index fragmentation on the primary key at scale; UUIDv7 keeps locality.
- **Per-table columns instead of shared bases.** Rejected: invites inconsistency
  exactly where consistency is a correctness/isolation property.
- **Hard deletes.** Rejected: leaders need alumni/history visibility, and sync
  needs tombstones to propagate removals — both require a logical-delete marker.
