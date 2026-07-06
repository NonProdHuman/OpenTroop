/**
 * Minimal synchronous SQL seam (GH-153 testing strategy).
 *
 * Satisfied by expo-sqlite on device (`expo-db.ts`) and by node:sqlite in
 * vitest (`test-db.ts`). A test seam, not a product abstraction — keep it to
 * exactly what the data layer uses.
 */

export type SqlParams = readonly (string | number | null)[]

export interface SqlDatabase {
  /** Execute DDL / statements without results. */
  exec(sql: string): void
  /** Run one statement with params (INSERT/UPDATE/DELETE). */
  run(sql: string, params?: SqlParams): void
  /** All result rows, as plain objects. */
  all<T = Record<string, unknown>>(sql: string, params?: SqlParams): T[]
  /** First result row or undefined. */
  get<T = Record<string, unknown>>(sql: string, params?: SqlParams): T | undefined
  /** Run `fn` inside BEGIN/COMMIT; ROLLBACK on throw. */
  transaction<T>(fn: () => T): T
}

/** Shared BEGIN/COMMIT wrapper for adapters whose driver lacks one. */
export function runInTransaction<T>(db: Omit<SqlDatabase, "transaction">, fn: () => T): T {
  db.exec("BEGIN")
  try {
    const result = fn()
    db.exec("COMMIT")
    return result
  } catch (error) {
    db.exec("ROLLBACK")
    throw error
  }
}
