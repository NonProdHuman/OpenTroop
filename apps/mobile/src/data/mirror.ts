import type { SqlDatabase } from "./db"
import type { SyncEntity } from "./schema"

/**
 * Mirror row application and reads (GH-153 §C1–C2).
 *
 * A pulled row with `is_deleted: true` hard-deletes the local copy — the
 * client never re-serves tombstones. Reads parse the stored JSON document;
 * cross-entity references use LEFT-JOIN semantics at the call site (a
 * dangling reference renders gracefully and heals on the next pull round).
 */

/** The minimal shape every sync payload row carries. */
export type SyncRow = {
  id: string
  sync_seq: number
  updated_at: string
  is_deleted: boolean
}

export type SyncCursor = { last_seq: number; last_id: string | null }

export function getCursor(db: SqlDatabase, entity: SyncEntity): SyncCursor {
  const row = db.get<{ last_seq: number; last_id: string | null }>(
    "SELECT last_seq, last_id FROM sync_state WHERE entity = ?",
    [entity],
  )
  return row ?? { last_seq: 0, last_id: null }
}

/**
 * Apply one pull page atomically: upsert/delete rows AND advance the cursor
 * in the same transaction, so a crash mid-sync resumes at the exact page
 * boundary (GH-153 §C2).
 */
export function applyPullPage(
  db: SqlDatabase,
  entity: SyncEntity,
  rows: SyncRow[],
  next: SyncCursor,
  epoch: number,
): void {
  db.transaction(() => {
    for (const row of rows) {
      if (row.is_deleted) {
        db.run(`DELETE FROM ${entity} WHERE id = ?`, [row.id])
      } else {
        db.run(
          `INSERT INTO ${entity} (id, sync_seq, updated_at, seen_epoch, data)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             sync_seq = excluded.sync_seq,
             updated_at = excluded.updated_at,
             seen_epoch = excluded.seen_epoch,
             data = excluded.data`,
          [row.id, row.sync_seq, row.updated_at, epoch, JSON.stringify(row)],
        )
      }
    }
    db.run(
      `INSERT INTO sync_state (entity, last_seq, last_id, last_synced_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(entity) DO UPDATE SET
         last_seq = excluded.last_seq,
         last_id = excluded.last_id,
         last_synced_at = excluded.last_synced_at`,
      [entity, next.last_seq, next.last_id, new Date().toISOString()],
    )
  })
}

/** Delete rows an epoch sweep did not see, then reset per-entity handled by caller. */
export function sweepStale(db: SqlDatabase, entity: SyncEntity, epoch: number): number {
  const before = db.get<{ n: number }>(`SELECT COUNT(*) AS n FROM ${entity}`)?.n ?? 0
  db.run(`DELETE FROM ${entity} WHERE seen_epoch < ?`, [epoch])
  const after = db.get<{ n: number }>(`SELECT COUNT(*) AS n FROM ${entity}`)?.n ?? 0
  return before - after
}

export function listRows<T>(db: SqlDatabase, entity: SyncEntity): T[] {
  return db
    .all<{ data: string }>(`SELECT data FROM ${entity} ORDER BY id`)
    .map((row) => JSON.parse(row.data) as T)
}

export function getRow<T>(db: SqlDatabase, entity: SyncEntity, id: string): T | null {
  const row = db.get<{ data: string }>(`SELECT data FROM ${entity} WHERE id = ?`, [id])
  return row ? (JSON.parse(row.data) as T) : null
}

/**
 * Write an interactive-API response row straight into the mirror (command
 * replay success path — the pull loop would deliver it anyway, this closes
 * the gap immediately). The response carries no sync_seq guarantee newer than
 * the mirror's, so keep the existing seq if the row is already present.
 */
export function upsertResponseRow(
  db: SqlDatabase,
  entity: SyncEntity,
  row: { id: string; updated_at?: string },
): void {
  const existing = db.get<{ sync_seq: number; seen_epoch: number }>(
    `SELECT sync_seq, seen_epoch FROM ${entity} WHERE id = ?`,
    [row.id],
  )
  db.run(
    `INSERT INTO ${entity} (id, sync_seq, updated_at, seen_epoch, data)
     VALUES (?, ?, ?, ?, ?)
     ON CONFLICT(id) DO UPDATE SET updated_at = excluded.updated_at, data = excluded.data`,
    [
      row.id,
      existing?.sync_seq ?? 0,
      row.updated_at ?? new Date().toISOString(),
      existing?.seen_epoch ?? 0,
      JSON.stringify(row),
    ],
  )
}
