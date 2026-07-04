import * as SQLite from "expo-sqlite"
import { runInTransaction, type SqlDatabase, type SqlParams } from "./db"
import { migrate } from "./schema"

/**
 * expo-sqlite adapter + per-tenant file management (GH-153 §C1/§C4).
 *
 * One database file per tenant; exactly one handle open at a time — the
 * active tenant's — so no query can cross tenants. Files persist as-of-last-
 * visit when switching troops; sign-out wipes them all (§C5).
 */

const dbFileName = (tenantId: string) => `opentroop-${tenantId}.db`

let open: { tenantId: string; db: SQLite.SQLiteDatabase } | null = null

function wrap(db: SQLite.SQLiteDatabase): SqlDatabase {
  const base = {
    exec: (sql: string) => db.execSync(sql),
    run: (sql: string, params: SqlParams = []) => {
      db.runSync(sql, params as (string | number | null)[])
    },
    all: <T>(sql: string, params: SqlParams = []) =>
      db.getAllSync<T>(sql, params as (string | number | null)[]),
    get: <T>(sql: string, params: SqlParams = []) =>
      db.getFirstSync<T>(sql, params as (string | number | null)[]) ?? undefined,
  }
  return { ...base, transaction: <T>(fn: () => T): T => runInTransaction(base, fn) }
}

/** Open (creating + migrating if needed) the active tenant's database. */
export function openTenantDatabase(tenantId: string): SqlDatabase {
  if (open && open.tenantId !== tenantId) closeTenantDatabase()
  if (!open) {
    const db = SQLite.openDatabaseSync(dbFileName(tenantId))
    db.execSync("PRAGMA journal_mode = WAL")
    open = { tenantId, db }
  }
  const wrapped = wrap(open.db)
  migrate(wrapped)
  return wrapped
}

export function closeTenantDatabase(): void {
  if (!open) return
  open.db.closeSync()
  open = null
}

/** Sign-out wipe (§C5): close and delete the given tenants' files. */
export function deleteTenantDatabases(tenantIds: string[]): void {
  closeTenantDatabase()
  for (const tenantId of tenantIds) {
    try {
      SQLite.deleteDatabaseSync(dbFileName(tenantId))
    } catch {
      // Never-created file: nothing to delete.
    }
  }
}
