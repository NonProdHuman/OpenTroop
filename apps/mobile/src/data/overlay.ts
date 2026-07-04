import type { PendingCommand } from "./commands"

/**
 * Optimistic overlay (GH-153 §C3): reads compose `mirror row + pending-command
 * effects folded on top` at query time. A pull that overwrites a row's base
 * state can't clobber local intent — the overlay re-applies on read, and an
 * entry vanishes when its command succeeds or is discarded.
 *
 * Only pending commands overlay; failed ones surface on Sync Issues instead
 * of silently masking server state.
 */

type EventLike = { id: string }
type ParticipantLike = { id: string; event_id: string; member_id: string }

export function overlayEvents<T extends EventLike>(
  events: T[],
  commands: PendingCommand[],
): T[] {
  const patches = new Map<string, Record<string, unknown>>()
  for (const cmd of commands) {
    if (cmd.state !== "pending" || cmd.kind !== "event.set_attendance_taken") continue
    const { event_id, ...fields } = cmd.payload
    patches.set(event_id, { ...patches.get(event_id), ...fields })
  }
  if (patches.size === 0) return events
  return events.map((event) =>
    patches.has(event.id) ? { ...event, ...patches.get(event.id) } : event,
  )
}

/**
 * Overlay participant updates and synthesize rows for pending creates.
 * A synthesized row gets id `pending:<command-id>` — replaced by the real row
 * once the create replays (or the next pull round delivers it).
 */
export function overlayParticipants<T extends ParticipantLike>(
  participants: T[],
  commands: PendingCommand[],
  makeBase: (payload: PendingCommand["payload"]) => T,
): T[] {
  const byTarget = new Map(participants.map((p) => [`${p.event_id}:${p.member_id}`, p]))
  const out: T[] = [...participants]

  for (const cmd of commands) {
    if (cmd.state !== "pending") continue
    if (cmd.kind !== "participant.update" && cmd.kind !== "participant.create") continue
    const { event_id, member_id, ...fields } = cmd.payload
    const key = `${event_id}:${member_id ?? ""}`
    const existing = byTarget.get(key)
    if (existing) {
      const patched = { ...existing, ...fields }
      out[out.indexOf(existing)] = patched
      byTarget.set(key, patched)
    } else if (cmd.kind === "participant.create") {
      const synthesized = { ...makeBase(cmd.payload), ...fields, id: `pending:${cmd.id}` }
      out.push(synthesized)
      byTarget.set(key, synthesized)
    }
    // participant.update against a row the mirror doesn't have yet: nothing to
    // patch — the row appears on the next pull round and the command replays
    // against the server regardless.
  }
  return out
}
