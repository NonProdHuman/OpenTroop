import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { openNodeDatabase } from "./node-db"
import { migrate } from "./schema"
import { getRow } from "./mirror"
import {
  drainQueue,
  enqueueCommand,
  listCommands,
  discardCommand,
  type HttpClient,
  type HttpResponse,
} from "./commands"

type Db = ReturnType<typeof openNodeDatabase>

let db: Db
beforeEach(() => {
  db = openNodeDatabase()
  migrate(db)
})
afterEach(() => db.close())

type Call = { path: string; method: string; body: unknown }

function fakeApi(responder: (call: Call) => HttpResponse | Error) {
  const calls: Call[] = []
  const http: HttpClient = async (path, init) => {
    const call = { path, method: init.method, body: init.body }
    calls.push(call)
    const result = responder(call)
    if (result instanceof Error) throw result
    return result
  }
  return { http, calls }
}

const ok = (body: unknown = {}): HttpResponse => ({ status: 200, body })

describe("enqueueCommand", () => {
  it("coalesces same-target commands in the original queue position", () => {
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", rsvp_status: "going" })
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m2", attended: true })
    // Flip-flop on the first target: merges into position 1, not position 3.
    enqueueCommand(db, "participant.update", {
      event_id: "e1",
      member_id: "m1",
      rsvp_status: "declined",
      guest_count: 2,
    })

    const pending = listCommands(db, "pending")
    expect(pending).toHaveLength(2)
    expect(pending[0].payload).toMatchObject({
      member_id: "m1",
      rsvp_status: "declined",
      guest_count: 2,
    })
    expect(pending[1].payload).toMatchObject({ member_id: "m2" })
  })
})

describe("drainQueue", () => {
  it("replays strictly FIFO — the attendance gate goes before the checkmarks", async () => {
    enqueueCommand(db, "event.set_attendance_taken", { event_id: "e1", attendance_taken: true })
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })
    const { http, calls } = fakeApi(() => ok())

    const result = await drainQueue(db, http)
    expect(result).toMatchObject({ sent: 2, failed: 0, halted: false })
    expect(calls.map((c) => `${c.method} ${c.path}`)).toEqual([
      "PATCH /events/e1",
      "PATCH /events/e1/participants/m1",
    ])
    expect(listCommands(db)).toHaveLength(0)
  })

  it("writes the response row into the mirror on success", async () => {
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })
    const { http } = fakeApi(() =>
      ok({ id: "p1", event_id: "e1", member_id: "m1", attended: true }),
    )
    await drainQueue(db, http)
    expect(getRow(db, "event_participants", "p1")).toMatchObject({ attended: true })
  })

  it("halts on transport errors and 5xx; the queue stays durable", async () => {
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m2", attended: true })

    let result = await drainQueue(db, fakeApi(() => new Error("offline")).http)
    expect(result).toMatchObject({ sent: 0, halted: true, needsAuth: false })
    expect(listCommands(db, "pending")).toHaveLength(2)

    result = await drainQueue(db, fakeApi(() => ({ status: 503, body: {} })).http)
    expect(result).toMatchObject({ sent: 0, halted: true })
    expect(listCommands(db, "pending")).toHaveLength(2)
  })

  it("pauses on 401 and flags re-auth", async () => {
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })
    const result = await drainQueue(db, fakeApi(() => ({ status: 401, body: {} })).http)
    expect(result).toMatchObject({ halted: true, needsAuth: true })
    expect(listCommands(db, "pending")).toHaveLength(1)
  })

  it("marks terminal 4xx failed with the server's reason and keeps draining", async () => {
    enqueueCommand(db, "participant.update", { event_id: "e1", member_id: "m1", attended: true })
    enqueueCommand(db, "participant.update", { event_id: "e2", member_id: "m1", rsvp_status: "going" })
    const { http } = fakeApi((call) =>
      call.path.includes("/e1/")
        ? { status: 409, body: { detail: "Attendance has not been taken for this event" } }
        : ok(),
    )

    const result = await drainQueue(db, http)
    expect(result).toMatchObject({ sent: 1, failed: 1, halted: false })
    const failed = listCommands(db, "failed")
    expect(failed).toHaveLength(1)
    expect(failed[0].last_error).toContain("Attendance has not been taken")
    // Discard clears it from Sync Issues.
    discardCommand(db, failed[0].id)
    expect(listCommands(db)).toHaveLength(0)
  })

  it("treats 409 on a replayed create as success", async () => {
    enqueueCommand(db, "participant.create", { event_id: "e1", member_id: "m1" })
    const { http, calls } = fakeApi(() => ({ status: 409, body: { detail: "duplicate" } }))
    const result = await drainQueue(db, http)
    expect(calls[0]).toMatchObject({ method: "POST", path: "/events/e1/participants" })
    expect(result).toMatchObject({ sent: 1, failed: 0 })
    expect(listCommands(db)).toHaveLength(0)
  })
})
