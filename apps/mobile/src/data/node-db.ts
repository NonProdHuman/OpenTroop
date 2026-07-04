import { DatabaseSync } from "node:sqlite"
import { runInTransaction, type SqlDatabase, type SqlParams } from "./db"

/**
 * node:sqlite adapter — TEST SEAM ONLY (vitest runs the data layer in Node).
 * Never import from app code; the device uses `expo-db.ts`.
 */
export function openNodeDatabase(path = ":memory:"): SqlDatabase & { close(): void } {
  const db = new DatabaseSync(path)
  const base = {
    exec: (sql: string) => db.exec(sql),
    run: (sql: string, params: SqlParams = []) => {
      db.prepare(sql).run(...(params as (string | number | null)[]))
    },
    all: <T>(sql: string, params: SqlParams = []) =>
      db.prepare(sql).all(...(params as (string | number | null)[])) as T[],
    get: <T>(sql: string, params: SqlParams = []) =>
      db.prepare(sql).get(...(params as (string | number | null)[])) as T | undefined,
  }
  return {
    ...base,
    transaction: <T>(fn: () => T): T => runInTransaction(base, fn),
    close: () => db.close(),
  }
}
