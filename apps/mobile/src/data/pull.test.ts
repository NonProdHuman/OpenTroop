import { afterEach, beforeEach, describe, expect, it } from "vitest"
import { openNodeDatabase } from "./node-db"
import { migrate } from "./schema"
import { getCursor, listRows } from "./mirror"
import { fullRefetch, pullRound } from "./pull"
import { enqueueCommand, listCommands, type HttpClient } from "./commands"

type Db = ReturnType<typeof openNodeDatabase>

let db: Db
beforeEach(() => {
  db = openNodeDatabase()
  migrate(db)
})
afterEach(() => db.close())

const row = (id: string, seq: number, extra: Record<string, unknown> = {}) => ({
  id,
  sync_seq: seq,
  updated_at: "2026-07-04T12:00:00Z",
  is_deleted: false,
  ...extra,
})

/**
 * Fake /sync server: `pages` maps an entity to a queue of page responses;
 * entities not listed serve one empty page. Records every request.
 */
function fakeSyncServer(pages: Record<string, object[]>) {
  const requests: string[] = []
  const remaining = new Map(Object.entries(pages).map(([k, v]) => [k, [...v]]))
  const http: HttpClient = async (path) => {
    requests.push(path)
    const entity = /\/sync\/(\w+)\?/.exec(path)?.[1] ?? ""
    const queue = remaining.get(entity)
    if (queue && queue.length > 0) {
      const page = queue.shift()
      if (page instanceof Error) throw page
      return { status: 200, body: page }
    }
    return {
      status: 200,
      body: { items: [], next_since_seq: 0, next_since_id: null, has_more: false },
    }
  }
  return { http, requests }
}

const page = (items: object[], nextSeq: number, nextId: string | null, hasMore: boolean) => ({
  items,
  next_since_seq: nextSeq,
  next_since_id: nextId,
  has_more: hasMore,
})

describe("pullRound", () => {
  it("applies pages and advances the cursor", async () => {
    const { http } = fakeSyncServer({
      members: [page([row("m1", 1), row("m2", 2)], 2, "m2", false)],
    })
    await pullRound(db, http)
    expect(listRows<{ id: string }>(db, "members").map((m) => m.id)).toEqual(["m1", "m2"])
    expect(getCursor(db, "members")).toEqual({ last_seq: 2, last_id: "m2" })
  })

  it("resumes at the exact page boundary after a mid-round crash", async () => {
    const boom = new Error("network down") as unknown as object
    const { http, requests } = fakeSyncServer({
      members: [page([row("m1", 1)], 1, "m1", true), boom as Error & object],
    })
    await expect(pullRound(db, http)).rejects.toThrow("network down")
    // Page 1 landed atomically with its cursor.
    expect(listRows(db, "members")).toHaveLength(1)
    expect(getCursor(db, "members")).toEqual({ last_seq: 1, last_id: "m1" })

    const retry = fakeSyncServer({ members: [page([row("m2", 2)], 2, "m2", false)] })
    await pullRound(db, retry.http)
    // The resume request carries the committed cursor — no skip, no re-pull.
    expect(retry.requests.find((r) => r.includes("/sync/members"))).toContain("since_seq=1")
    expect(retry.requests.find((r) => r.includes("/sync/members"))).toContain("since_id=m1")
    expect(listRows<{ id: string }>(db, "members").map((m) => m.id)).toEqual(["m1", "m2"])
    expect(requests.length).toBeGreaterThan(0)
  })

  it("hard-deletes on tombstones", async () => {
    const { http } = fakeSyncServer({
      events: [page([row("e1", 1), row("e2", 2)], 2, "e2", false)],
    })
    await pullRound(db, http)
    const second = fakeSyncServer({
      events: [page([row("e1", 3, { is_deleted: true })], 3, "e1", false)],
    })
    await pullRound(db, second.http)
    expect(listRows<{ id: string }>(db, "events").map((e) => e.id)).toEqual(["e2"])
  })

  it("pulls entities in dependency order", async () => {
    const { http, requests } = fakeSyncServer({})
    await pullRound(db, http)
    const order = requests.map((r) => /\/sync\/(\w+)\?/.exec(r)?.[1])
    expect(order).toEqual([
      "event_types",
      "locations",
      "members",
      "member_relationships",
      "events",
      "event_participants",
      "inbox_messages",
      "inbox_recipients",
    ])
  })
})

describe("fullRefetch (mark-and-sweep)", () => {
  it("removes rows the sweep did not see; pending commands survive", async () => {
    const { http } = fakeSyncServer({
      events: [page([row("e-visible", 1), row("e-lost", 2)], 2, "e-lost", false)],
    })
    await pullRound(db, http)
    enqueueCommand(db, "event.set_attendance_taken", {
      event_id: "e-visible",
      attendance_taken: true,
    })

    // The refetch walks from zero; the server no longer serves e-lost
    // (visibility revoked — no tombstone ever comes).
    const refetch = fakeSyncServer({
      events: [page([row("e-visible", 1)], 2, "e-lost", false)],
    })
    const removed = await fullRefetch(db, refetch.http)
    expect(removed).toBe(1)
    expect(listRows<{ id: string }>(db, "events").map((e) => e.id)).toEqual(["e-visible"])
    expect(refetch.requests.find((r) => r.includes("/sync/events"))).toContain("since_seq=0")
    expect(listCommands(db, "pending")).toHaveLength(1)
  })
})
