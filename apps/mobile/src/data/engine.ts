import type { SqlDatabase } from "./db"
import { drainQueue, type DrainResult, type HttpClient } from "./commands"
import { fullRefetch, pullRound } from "./pull"
import { getMeta } from "./schema"

/**
 * Sync orchestration (GH-153): drain the outbox first (our intent reaches the
 * server before we read back), then pull a round so the mirror picks up both
 * our replayed writes and everyone else's changes.
 */

export type SyncOutcome = {
  drain: DrainResult
  pulled: boolean
  error: string | null
}

const FULL_REFETCH_INTERVAL_MS = 7 * 24 * 60 * 60 * 1000 // ~weekly, opportunistic

export async function syncNow(
  db: SqlDatabase,
  http: HttpClient,
  { full = false }: { full?: boolean } = {},
): Promise<SyncOutcome> {
  const drain = await drainQueue(db, http)
  try {
    if (full || fullRefetchDue(db)) {
      await fullRefetch(db, http)
    } else {
      await pullRound(db, http)
    }
    return { drain, pulled: true, error: null }
  } catch (error) {
    // Offline or a mid-round failure: the last committed page boundary holds;
    // the next round resumes from there.
    return { drain, pulled: false, error: error instanceof Error ? error.message : String(error) }
  }
}

export function fullRefetchDue(db: SqlDatabase): boolean {
  const last = getMeta(db, "last_full_refetch_at")
  if (!last) return false // the very first pull already walks from seq 0
  return Date.now() - Date.parse(last) > FULL_REFETCH_INTERVAL_MS
}
