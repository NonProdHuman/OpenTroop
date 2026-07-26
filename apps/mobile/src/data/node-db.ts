/// <reference types="node" />
// TypeScript 6 (SDK 57) no longer auto-includes @types/node here, and the
// reference is kept file-local on purpose: this is the only module that runs
// in Node, so device code stays free of Node globals.
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
