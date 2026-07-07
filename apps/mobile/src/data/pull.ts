import type { SqlDatabase } from "./db"
import type { HttpClient } from "./commands"
import { SYNC_ENTITIES, type SyncEntity, getMeta, setMeta } from "./schema"
import { applyPullPage, getCursor, sweepStale, type SyncRow } from "./mirror"

/**
 * The pull loop (GH-153 §C2): consume the /sync/* keyset streams into the
 * mirror. One round pulls each entity to completion in dependency order; each
 * page is applied atomically with its cursor, so a killed app resumes at the
 * exact page boundary.
 */

type SyncPage = {
  items: SyncRow[]
  next_since_seq: number
  next_since_id: string | null
  has_more: boolean
}

const PAGE_LIMIT = 500
const EPOCH_KEY = "sync_epoch"

export function currentEpoch(db: SqlDatabase): number {
  return Number(getMeta(db, EPOCH_KEY) ?? "1")
}

async function pullEntity(
  db: SqlDatabase,
  http: HttpClient,
  entity: SyncEntity,
  epoch: number,
  fromZero: boolean,
): Promise<void> {
  let cursor = fromZero ? { last_seq: 0, last_id: null } : getCursor(db, entity)
  for (;;) {
    const params = new URLSearchParams({
      since_seq: String(cursor.last_seq),
      limit: String(PAGE_LIMIT),
    })
    if (cursor.last_id) params.set("since_id", cursor.last_id)
    const response = await http(`/sync/${entity}?${params}`, { method: "GET" })
    if (response.status >= 400) throw new PullError(entity, response.status)
    const page = response.body as SyncPage | null
    if (!page || !Array.isArray(page.items) || typeof page.next_since_seq !== "number") {
      throw new Error(`Sync pull for ${entity} returned a malformed page`)
    }
    const prev = cursor
    cursor = { last_seq: page.next_since_seq, last_id: page.next_since_id }
    applyPullPage(db, entity, page.items, cursor, epoch)
    if (!page.has_more) return
    if (cursor.last_seq === prev.last_seq && cursor.last_id === prev.last_id) {
      // A server bug must fail the round, not spin the request loop forever.
      throw new Error(`Sync pull for ${entity} is not advancing its cursor`)
    }
  }
}

export class PullError extends Error {
  constructor(
    public readonly entity: SyncEntity,
    public readonly status: number,
  ) {
    super(`Sync pull for ${entity} failed with HTTP ${status}`)
    this.name = "PullError"
  }
}

/** One incremental round: every entity to completion, dependency order. */
export async function pullRound(db: SqlDatabase, http: HttpClient): Promise<void> {
  const epoch = currentEpoch(db)
  for (const entity of SYNC_ENTITIES) {
    await pullEntity(db, http, entity, epoch, false)
  }
  setMeta(db, "last_pull_at", new Date().toISOString())
}

/**
 * Full refetch (mark-and-sweep, GH-153 §C2): bump the epoch, walk every
 * entity from since_seq=0 stamping rows, and on successful completion delete
 * rows the sweep didn't see (missed tombstones, lost visibility). Never shows
 * an empty database — the mirror stays readable throughout. Pending commands
 * are untouched.
 */
export async function fullRefetch(db: SqlDatabase, http: HttpClient): Promise<number> {
  const epoch = currentEpoch(db) + 1
  setMeta(db, EPOCH_KEY, String(epoch))
  for (const entity of SYNC_ENTITIES) {
    await pullEntity(db, http, entity, epoch, true)
  }
  let removed = 0
  for (const entity of SYNC_ENTITIES) {
    removed += sweepStale(db, entity, epoch)
  }
  setMeta(db, "last_full_refetch_at", new Date().toISOString())
  return removed
}
