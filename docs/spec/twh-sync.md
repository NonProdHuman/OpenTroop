# TroopWebHost Sync Strategy Spec

**Status:** Draft — provenance groundwork shipped; sync engine deferred
**Pillar:** Migration & Onboarding (cross-cutting)
**Related:** [`position-history.md`](position-history.md) · backend importer `app/importers/twh.py`

---

## Overview

The TWH importer (`app/importers/twh.py`) is a **one-shot bootstrap**: it parses a full
TroopWebHost XML export and inserts a tenant's roster, events, and leadership. Re-running
it does **not** update existing rows — it mints new UUIDs and would either collide on the
BSA unique index or create duplicates.

Troops will realistically **dual-run TWH and OpenTroop in parallel for a few months** while
they test the waters. During that window TWH stays the source of truth for data troops keep
maintaining there (new members, leadership changes, event sign-ups), and OpenTroop needs to
**pull those changes incrementally** rather than demanding a single hard cut-over.

This spec records the strategy for that incremental sync and defines the **groundwork
shipped now** so the capability can be built later without a data migration. It does **not**
build the sync engine — that's a deferred, larger effort whose hard parts are conflict
policy and deletes, not parsing.

---

## Decision: XML is the sync substrate, not CSV

TWH offers per-dataset CSV exports as well as the full XML. For incremental sync the **full
XML is the better source**, because it already carries the signals a sync needs:

- **`Last_Update_UTC`** — a per-row last-modified timestamp on most records. This is the
  "what changed since my last sync" key and the conflict-resolution signal.
- **Delete/audit tables** — `Delete_Audit` (`Table_Name` / `Row_ID` / `Delete_UTC`),
  `Database_Action`, and `*_Audit` rows. TWH exports a change log **and tombstones for
  deletes**, so deletions are detectable explicitly rather than inferred from absence.
- **Referential completeness** — every entity and its foreign keys in one document.

CSV datasets are flat snapshots: they generally lack delete signals and cross-entity
integrity, so they're best reserved for **targeted single-dataset refreshes** ("re-pull just
the roster"), not a general sync. We keep CSV in our back pocket; we don't anchor sync on it.

The format was never the blocker. The real work is **(1) stable identity across runs** and
**(2) conflict policy** — both format-independent. Item (1) is the groundwork below.

---

## Groundwork shipped now: source provenance

A `SourceTracked` mixin (`app/models/base.py`) adds three **nullable** columns, applied
alongside `TrackedBase` to the nine entities the importer creates (`Group`, `Member`,
`MemberRelationship`, `Location`, `EventType`, `Event`, `EventParticipant`, `Position`,
`MemberPositionAssignment`):

| Column | Type | Meaning |
|---|---|---|
| `source_system` | `str?` (32) | Originating system — `"twh"`. NULL for natively-created rows. |
| `source_id` | `str?` (64), indexed | That system's stable record id — the TWH `<i>`. The match key for upsert. |
| `source_updated_at` | `datetime?` (tz-aware) | The source's own last-modified time — TWH `Last_Update_UTC` (already UTC; parsed without the wall-clock timezone shift). |

The importer populates them on every row it creates (`TwhImporter._source`):
`source_id` from the record's `<i>` (catalog id for `Position`, history-row id for
`MemberPositionAssignment`), `source_updated_at` from `Last_Update_UTC` when present.

**Why now:** capturing provenance is additive and cheap, but it's the one thing that is
**painful to retrofit** — a past import that discarded the TWH id can't be reconciled later
without re-importing. Shipping these columns means today's bootstrap imports are
*upgradeable* into a synced dataset instead of orphaned. Nothing reads them yet.

Migration `e2f3a4b5c6d7` adds the columns + a per-table `source_id` index. No new tables, so
RLS is unaffected.

> **Not yet added (deferred to the sync build):** a partial unique index on
> `(tenant_id, source_system, source_id)`. It's the right long-term guard against duplicate
> upserts, but it's only meaningful once the upsert path exists, and adding it now would
> constrain the current additive importer for no benefit. Noted here so it isn't forgotten.

---

## Sync engine (deferred — design sketch)

When built, an incremental sync pass over a fresh XML export would, per entity type:

1. **Match** each source record by `(tenant_id, source_system="twh", source_id)`.
2. **Insert** when no match exists (new upstream record).
3. **Update** when matched *and* the source changed — gate on
   `source_updated_at` advancing past the stored value to skip untouched rows cheaply.
4. **Delete** (soft) from TWH's `Delete_Audit` / `Delete_UTC` tombstones — never by mere
   absence, and never touching rows with `source_system IS NULL` (locally-created data).

Entities are processed in the existing dependency order; the in-memory `source_id → UUID`
maps the importer already builds become persistent lookups against the indexed columns.

### Conflict policy (the genuinely hard part — open)

Once a troop edits a record in OpenTroop, a re-sync must decide who wins. Options, roughly
increasing in effort:

- **TWH-authoritative** — TWH overwrites on every sync. Simplest; correct while TWH is the
  system of record, but silently clobbers OpenTroop edits.
- **Last-writer-wins** — compare TWH `source_updated_at` against OpenTroop `updated_at`;
  newer wins. Needs a reliable local "touched at" and tolerates clock skew poorly.
- **Field-level ownership** — TWH owns roster/leadership fields, OpenTroop owns
  OpenTroop-only fields (calendar tokens, group rules, claims). Most correct for dual-run,
  most work.

**Leaning:** during dual-run, **TWH-authoritative for the fields TWH manages**, with a
per-row "locally edited" guard so OpenTroop-only state (claims, calendar tokens, group
membership, audiences) is never overwritten. Finalize when the engine is built.

---

## Identity edge cases

- **Members without a `bsa_id`** (parents, non-registered) — `source_id` (the TWH Person
  `<i>`) is the identity key, not BSA number, so these sync fine where BSA matching couldn't.
- **The admin appears in the XML** — today the importer creates a *second* member row for a
  Clerk-linked admin who's also a `Person`. With `source_id` captured, a future sync (or a
  small importer tweak) can **link onto the existing admin** by matching provenance instead
  of duplicating. Tracked as a follow-up.
- **Positions** — matched to OpenTroop positions by the deterministic slug → BSA code
  crosswalk (see `position-history.md`); `Position.source_id` records the originating TWH
  catalog id for traceability.

---

## Non-goals (now)

- No sync engine, scheduler, or upsert path — provenance columns only.
- No CSV ingestion.
- No bidirectional sync (OpenTroop → TWH is out of scope entirely).
- No UI for sync status/conflicts.

## Open questions

1. **Conflict policy** — confirm TWH-authoritative-with-local-guard vs field-level ownership
   (see above) when the engine is built.
2. **Sync trigger** — admin-initiated re-upload of an export vs. a scheduled pull. TWH has no
   public API, so this is likely "admin uploads a fresh export," reusing `POST /import/twh`
   in an upsert mode.
3. **Admin de-duplication** — link an imported `Person` onto an existing Clerk-linked member
   by provenance/BSA, or leave as a manual merge.
4. **Partial unique index** on `(tenant_id, source_system, source_id)` — add with the upsert
   path; confirm it shouldn't also cover the current importer.
