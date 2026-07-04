import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { openNodeDatabase } from "./node-db"
import { migrate } from "./schema"
import { applyPullPage, listRows } from "./mirror"
import { enqueueCommand, listCommands } from "./commands"
import { overlayEvents, overlayParticipants } from "./overlay"

type Db = ReturnType<typeof openNodeDatabase>

let db: Db
beforeEach(() => {
  db = openNodeDatabase()
  migrate(db)
})
afterEach(() => db.close())

type P = {
  id: string
  event_id: string
  member_id: string
  attended?: boolean | null
  rsvp_status?: string
  sync_seq: number
  updated_at: string
  is_deleted: boolean
}

const participant = (id: string, member: string, seq: number, extra = {}): P => ({
  id,
  event_id: "e1",
  member_id: member,
  sync_seq: seq,
  updated_at: "2026-07-04T10:00:00Z",
  is_deleted: false,
  ...extra,
})

describe("optimistic overlay", () => {
  it("survives a pull that rewrites the base row (the Sunday-at-camp case)", () => {
    applyPullPage(db, "event_participants", [participant("p1", "m1", 1)], { last_seq: 1, last_id: "p1" }, 1)
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })

    // Someone at home edits while we're offline: a later pull rewrites the row.
    applyPullPage(
      db,
      "event_participants",
      [participant("p1", "m1", 5, { rsvp_status: "going" })],
      { last_seq: 5, last_id: "p1" },
      1,
    )

    const rows = overlayParticipants(
      listRows<P>(db, "event_participants"),
      listCommands(db),
      (payload) => participant("base", String(payload.member_id), 0),
    )
    // The local intent re-applies on read; the pulled edit is not clobbered.
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ attended: true, rsvp_status: "going" })
  })

  it("synthesizes a row for a pending create and patches events", () => {
    enqueueCommand(db, "participant.create", { event_id: "e1", member_id: "m9", rsvp_status: "going" })
    const rows = overlayParticipants([] as P[], listCommands(db), (payload) =>
      participant("ignored", String(payload.member_id), 0),
    )
    expect(rows).toHaveLength(1)
    expect(rows[0].id).toMatch(/^pending:/)
    expect(rows[0]).toMatchObject({ member_id: "m9", rsvp_status: "going" })

    enqueueCommand(db, "event.set_attendance_taken", { event_id: "e1", attendance_taken: true })
    const events = overlayEvents(
      [{ id: "e1", attendance_taken: false }, { id: "e2", attendance_taken: false }],
      listCommands(db),
    )
    expect(events[0]).toMatchObject({ id: "e1", attendance_taken: true })
    expect(events[1]).toMatchObject({ id: "e2", attendance_taken: false })
  })

  it("failed commands do not overlay (they surface on Sync Issues instead)", () => {
    const cmd = enqueueCommand(db, "event.set_attendance_taken", {
      event_id: "e1",
      attendance_taken: true,
    })
    db.run("UPDATE pending_commands SET state = 'failed' WHERE id = ?", [cmd.id])
    const events = overlayEvents([{ id: "e1", attendance_taken: false }], listCommands(db))
    expect(events[0]).toMatchObject({ attendance_taken: false })
  })
})
