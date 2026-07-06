# 0010. Hard delete: anonymize-then-reap for members, export-gated immediate purge for tenants

- **Status:** Accepted
- **Date:** 2026-07-05

## Context

Deletion was soft everywhere: `is_deleted` tombstones, member statuses, tenant
suspension. Nothing actually removed data — a right-to-erasure problem (COPPA/GDPR;
we hold minors' medical data) and, over years, unbounded retention. But naive
physical deletion fights two load-bearing designs:

- **Offline sync** (ADR 0002, sync-protocol Decision 5): clients mirror rows via
  `sync_seq` cursors and learn about deletions from tombstones. A row that is
  physically deleted simply vanishes from the change stream — devices would keep
  the purged PII forever, defeating the erasure.
- **History integrity:** attendance counts, advancement records, and position
  history reference members. Cascading a member away on day 0 silently rewrites
  the troop's past.

Tenant deletion has a different failure mode: one confirmed mistake destroys an
entire troop, and there was no export to fall back on (#121 not yet built).

## Decision

**Members: anonymize immediately, reap later.** `POST /members/{id}/purge`
(admin-only, type-the-full-name confirmation) nulls every PII field in place —
the row becomes a faceless soft-deleted tombstone (`purged_at` stamped) that
rides the normal sync stream, so erasure is complete on day 0 while attendance
and advancement history stay truthful. After `TOMBSTONE_RETENTION_DAYS`
(default 180 — the Decision 5 floor; config validator refuses less) the reaper
(`uv run reap-tombstones`) physically deletes the skeleton row and its
dependents, nulls surviving back-references, and records a fresh
`Tenant.purged_through_seq` watermark drawn from the `sync_seq` sequence. The
pull endpoints answer **410** to any cursor behind the watermark (full-refetch
required) and clamp a completed walk's cursor up to it — this is what makes
hard-deleting never-tombstoned dependent rows (participants, completions) safe
for incremental sync. The reaper touches **only** purged members: general
tombstone retention is #121, and revoked advancement rows must never be
physically deleted (the auto-credit engine treats their existence as "do not
re-create").

**Tenants: immediate purge behind three gates.** `DELETE /platform/tenants/{id}`
(superadmin) requires the tenant to be suspended, a full JSON export
(`GET /platform/tenants/{id}/export`, stamps `last_export_at`) taken **after**
the suspension, and the slug echoed in the body. The purge walks every
`tenant_id` table in reverse FK order in one transaction; platform
`User`/`Identity` rows survive. No grace window: the mandatory export **is** the
recovery path (re-provision + re-import), and immediate deletion frees the slug
at once for re-provisioning.

## Consequences

- Erasure is immediate and provable, yet offline mirrors converge through the
  ordinary tombstone stream — no special client code for purges.
- A reap forces a one-time full refetch for the tenant's devices (the watermark
  deliberately dominates every issued cursor). Reaps are rare and troop datasets
  are small; we accept the refetch over dangling rows on devices.
- Aggregate history (attendance totals, advancement) survives 180 days
  anonymized, then goes with the reap — long-term aggregates must not depend on
  purged members.
- `Message.sent_by_id` became nullable; UIs must render a null sender as a
  deleted member.
- Tenant deletion is recoverable only via the exported bundle; #121's import
  side is what will make that restore path convenient.

## Alternatives considered

- **Full cascaded row removal on day 0** — breaks sync tombstoning (devices keep
  PII), fights the FK graph, rewrites history instantly.
- **Anonymize forever (no reaper)** — unbounded skeleton-row growth; the DB
  never actually forgets.
- **Tenant grace window ("scheduled deletion")** — safer-feeling, but it blocks
  slug reuse (or demands slug-tombstone gymnastics) and adds scheduled state; the
  mandatory export gives equivalent recoverability with none of that.
- **Per-stream tombstones for reaped dependents** — a second deferred tombstone
  cycle per dependent table; the single watermark + full refetch is one rule.
