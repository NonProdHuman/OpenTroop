import type { SqlDatabase } from "./db"

/**
 * Local schema for one tenant's database file (GH-153 §C1).
 *
 * Mirror tables are JSON documents with extracted cursor columns — the client
 * is a replica, not a system of record, so additive server fields need no
 * local migration. Local migrations (bump SCHEMA_VERSION) are limited to
 * index/column changes; an unknown older version falls back to
 * rebuild-and-refetch, preserving pending_commands.
 */

export const SCHEMA_VERSION = 2

/** Sync entities in dependency order (GH-153 §C2). Values are /sync paths. */
export const SYNC_ENTITIES = [
  "event_types",
  "locations",
  "members",
  "member_relationships",
  "events",
  "event_participants",
  "inbox_messages",
  "inbox_recipients",
] as const

export type SyncEntity = (typeof SYNC_ENTITIES)[number]

const MIRROR_TABLE_DDL = (table: string) => `
  CREATE TABLE IF NOT EXISTS ${table} (
    id         TEXT PRIMARY KEY,
    sync_seq   INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    seen_epoch INTEGER NOT NULL DEFAULT 0,
    data       TEXT NOT NULL
  );
`

export function migrate(db: SqlDatabase): void {
  const row = db.get<{ user_version: number }>("PRAGMA user_version")
  const current = row?.user_version ?? 0
  if (current === SCHEMA_VERSION) return
  if (current > SCHEMA_VERSION) {
    // Downgraded app against a newer file: rebuild (pending commands survive).
    rebuildMirror(db)
  }

  db.transaction(() => {
    for (const entity of SYNC_ENTITIES) db.exec(MIRROR_TABLE_DDL(entity))
    db.exec(`
      CREATE TABLE IF NOT EXISTS sync_state (
        entity         TEXT PRIMARY KEY,
        last_seq       INTEGER NOT NULL DEFAULT 0,
        last_id        TEXT,
        last_synced_at TEXT
      );
    `)
    db.exec(`
      CREATE TABLE IF NOT EXISTS pending_commands (
        id         TEXT PRIMARY KEY,
        position   INTEGER NOT NULL,
        kind       TEXT NOT NULL,
        target_key TEXT NOT NULL,
        payload    TEXT NOT NULL,
        state      TEXT NOT NULL DEFAULT 'pending',
        attempts   INTEGER NOT NULL DEFAULT 0,
        last_error TEXT,
        created_at TEXT NOT NULL
      );
    `)
    db.exec("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);")
    db.exec(`PRAGMA user_version = ${SCHEMA_VERSION}`)
  })
}

/** Drop and recreate all mirror + cursor tables. Pending commands survive. */
export function rebuildMirror(db: SqlDatabase): void {
  db.transaction(() => {
    for (const entity of SYNC_ENTITIES) db.exec(`DROP TABLE IF EXISTS ${entity}`)
    db.exec("DROP TABLE IF EXISTS sync_state")
    db.exec("PRAGMA user_version = 0")
  })
}

export function getMeta(db: SqlDatabase, key: string): string | null {
  return db.get<{ value: string }>("SELECT value FROM meta WHERE key = ?", [key])?.value ?? null
}

export function setMeta(db: SqlDatabase, key: string, value: string): void {
  db.run(
    "INSERT INTO meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
    [key, value],
  )
}
