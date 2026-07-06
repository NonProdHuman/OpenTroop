import type { SqlDatabase } from "./db"
import { errorDetail } from "../lib/http"
import { upsertResponseRow } from "./mirror"

/**
 * The offline outbox (GH-153 §C3): typed commands replayed FIFO through the
 * existing interactive API when connectivity returns. Every server-side check
 * (permission, attendance gate, signup window) runs at execution time exactly
 * as if the user were online.
 */

export type CommandKind =
  | "event.set_attendance_taken"
  | "participant.update"
  | "participant.create"

export type CommandPayload = Record<string, unknown> & {
  event_id: string
  member_id?: string
}

export type PendingCommand = {
  id: string
  position: number
  kind: CommandKind
  target_key: string
  payload: CommandPayload
  state: "pending" | "failed"
  attempts: number
  last_error: string | null
  created_at: string
}

export type HttpResponse = { status: number; body: unknown }
/** Network seam: throws on transport failure; resolves with status for HTTP errors. */
export type HttpClient = (
  path: string,
  init: { method: string; body?: unknown },
) => Promise<HttpResponse>

/** Where a successful replay's response row lands, per kind. */
const RESPONSE_ENTITY = {
  "event.set_attendance_taken": "events",
  "participant.update": "event_participants",
  "participant.create": "event_participants",
} as const

function buildRequest(cmd: PendingCommand): { path: string; method: string; body: unknown } {
  const { event_id, member_id, ...fields } = cmd.payload
  switch (cmd.kind) {
    case "event.set_attendance_taken":
      return { path: `/events/${event_id}`, method: "PATCH", body: fields }
    case "participant.update":
      return {
        path: `/events/${event_id}/participants/${member_id}`,
        method: "PATCH",
        body: fields,
      }
    case "participant.create":
      return {
        path: `/events/${event_id}/participants`,
        method: "POST",
        body: { member_id, ...fields },
      }
  }
}

/** Stable identity for coalescing: one queued command per (kind, target). */
export function targetKey(kind: CommandKind, payload: CommandPayload): string {
  return kind === "event.set_attendance_taken"
    ? payload.event_id
    : `${payload.event_id}:${payload.member_id ?? ""}`
}

function newCommandId(): string {
  const cryptoApi = globalThis.crypto
  if (cryptoApi?.randomUUID) return cryptoApi.randomUUID()
  // Fallback for runtimes without WebCrypto: local-only queue id, not a server id.
  return `cmd-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

/**
 * Enqueue a command, coalescing with an earlier pending command for the same
 * (kind, target): the payload merges *in the original queue position* so
 * RSVP flip-flopping offline yields one command and cross-target ordering is
 * preserved (GH-153 §C3).
 */
export function enqueueCommand(
  db: SqlDatabase,
  kind: CommandKind,
  payload: CommandPayload,
): PendingCommand {
  const key = targetKey(kind, payload)
  return db.transaction(() => {
    const existing = db.get<{ id: string; payload: string }>(
      "SELECT id, payload FROM pending_commands WHERE kind = ? AND target_key = ? AND state = 'pending'",
      [kind, key],
    )
    if (existing) {
      const merged = { ...(JSON.parse(existing.payload) as CommandPayload), ...payload }
      db.run("UPDATE pending_commands SET payload = ? WHERE id = ?", [
        JSON.stringify(merged),
        existing.id,
      ])
      return getCommand(db, existing.id)
    }
    const max = db.get<{ p: number | null }>("SELECT MAX(position) AS p FROM pending_commands")
    const cmd: PendingCommand = {
      id: newCommandId(),
      position: (max?.p ?? 0) + 1,
      kind,
      target_key: key,
      payload,
      state: "pending",
      attempts: 0,
      last_error: null,
      created_at: new Date().toISOString(),
    }
    db.run(
      `INSERT INTO pending_commands (id, position, kind, target_key, payload, state, attempts, last_error, created_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [cmd.id, cmd.position, cmd.kind, cmd.target_key, JSON.stringify(cmd.payload), cmd.state, 0, null, cmd.created_at],
    )
    return cmd
  })
}

function parseCommand(row: Record<string, unknown>): PendingCommand {
  return {
    ...(row as Omit<PendingCommand, "payload">),
    payload: JSON.parse(row.payload as string) as CommandPayload,
  }
}

export function getCommand(db: SqlDatabase, id: string): PendingCommand {
  const row = db.get("SELECT * FROM pending_commands WHERE id = ?", [id])
  if (!row) throw new Error(`Unknown command ${id}`)
  return parseCommand(row)
}

export function listCommands(
  db: SqlDatabase,
  state?: "pending" | "failed",
): PendingCommand[] {
  const rows = state
    ? db.all("SELECT * FROM pending_commands WHERE state = ? ORDER BY position", [state])
    : db.all("SELECT * FROM pending_commands ORDER BY position")
  return rows.map(parseCommand)
}

export function discardCommand(db: SqlDatabase, id: string): void {
  db.run("DELETE FROM pending_commands WHERE id = ?", [id])
}

export type DrainResult = {
  sent: number
  failed: number
  /** True when the drain stopped early (offline / 5xx / auth) — retry later. */
  halted: boolean
  /** The queue paused on a 401 — prompt re-auth (GH-153 §C5). */
  needsAuth: boolean
}

/**
 * Drain the queue strictly FIFO (GH-153 §C3):
 * - transport errors and 5xx halt the drain (the queue is durable; retry later);
 * - 401 halts and flags re-auth;
 * - other 4xx mark the command failed (Sync Issues) and continue;
 * - 409 on a replayed create is success (idempotent-by-construction);
 * - success writes the response row straight into the mirror.
 */
export async function drainQueue(db: SqlDatabase, http: HttpClient): Promise<DrainResult> {
  const result: DrainResult = { sent: 0, failed: 0, halted: false, needsAuth: false }
  for (const cmd of listCommands(db, "pending")) {
    const request = buildRequest(cmd)
    let response: HttpResponse
    try {
      response = await http(request.path, { method: request.method, body: request.body })
    } catch {
      result.halted = true
      return result
    }

    if (response.status === 401) {
      result.halted = true
      result.needsAuth = true
      return result
    }
    if (response.status >= 500) {
      result.halted = true
      return result
    }

    const created409 = cmd.kind === "participant.create" && response.status === 409
    if (response.status < 400 || created409) {
      db.transaction(() => {
        if (!created409 && response.body && typeof response.body === "object") {
          const row = response.body as { id?: string; updated_at?: string }
          if (row.id) {
            upsertResponseRow(db, RESPONSE_ENTITY[cmd.kind], row as { id: string })
          }
        }
        discardCommand(db, cmd.id)
      })
      result.sent += 1
      continue
    }

    // Terminal 4xx: visible failure, keep draining (later commands for other
    // targets are independent; dependent ones fail with the server's reason).
    db.run(
      "UPDATE pending_commands SET state = 'failed', attempts = attempts + 1, last_error = ? WHERE id = ?",
      [errorDetail(response.body, response.status), cmd.id],
    )
    result.failed += 1
  }
  return result
}
